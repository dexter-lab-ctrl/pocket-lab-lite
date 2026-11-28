[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidateRange(1024, 65535)]
  [int]$ListenPort,

  [Parameter(Mandatory = $true)]
  [ValidatePattern('^(127\.0\.0\.1|10\.(?:[0-9]{1,3}\.){2}[0-9]{1,3}|172\.(?:1[6-9]|2[0-9]|3[01])\.(?:[0-9]{1,3}\.)[0-9]{1,3}|192\.168\.(?:[0-9]{1,3}\.)[0-9]{1,3})$')]
  [string]$TargetHost,

  [Parameter(Mandatory = $true)]
  [ValidateRange(1024, 65535)]
  [int]$TargetPort,

  [ValidateRange(1, 64)]
  [int]$MaxConcurrentRequests = 16
)

<#
.SYNOPSIS
  Bounded, standard-user Windows bridge for an isolated Pocket Lab candidate.

.DESCRIPTION
  Tailscale Serve on Windows cannot always reach a WSL loopback listener. This
  bridge keeps the browser-facing listener on Windows loopback and forwards to
  one explicitly supplied private WSL address. It is qualification transport,
  not an application runtime or a public proxy.

  The implementation uses a small compiled .NET listener so long-lived SSE
  responses cannot occupy the request loop. Set-Cookie is copied one header at
  a time because joining cookie headers changes their meaning and can drop the
  short-lived owner setup authority.
#>

$ErrorActionPreference = 'Stop'

$source = @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;

public static class PocketLabQualificationHttpsBridge
{
    private const long MaxBodyBytes = 16L * 1024L * 1024L;
    private static readonly HashSet<string> HopByHop = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
    {
        "Connection", "Content-Length", "Keep-Alive", "Proxy-Authenticate",
        "Proxy-Authorization", "Proxy-Connection", "TE", "Trailer",
        "Transfer-Encoding", "Upgrade", "Host"
    };

    public static void Run(int listenPort, string targetHost, int targetPort, int maxConcurrentRequests)
    {
        var listener = new HttpListener();
        listener.Prefixes.Add("http://127.0.0.1:" + listenPort + "/");
        listener.Start();

        var handler = new HttpClientHandler
        {
            AllowAutoRedirect = false,
            UseCookies = false,
            AutomaticDecompression = System.Net.DecompressionMethods.None
        };
        var client = new HttpClient(handler)
        {
            Timeout = TimeSpan.FromMinutes(10)
        };
        var gate = new SemaphoreSlim(maxConcurrentRequests, maxConcurrentRequests);

        try
        {
            while (true)
            {
                var context = listener.GetContext();
                if (!gate.Wait(0))
                {
                    context.Response.StatusCode = 503;
                    context.Response.ContentLength64 = 0;
                    context.Response.Close();
                    continue;
                }
                Task.Run(() =>
                {
                    try { Handle(context, client, targetHost, targetPort); }
                    finally { gate.Release(); }
                });
            }
        }
        finally
        {
            try { listener.Stop(); } catch { }
            try { listener.Close(); } catch { }
            client.Dispose();
            handler.Dispose();
            gate.Dispose();
        }
    }

    private static void Handle(HttpListenerContext context, HttpClient client, string targetHost, int targetPort)
    {
        HttpRequestMessage request = null;
        HttpResponseMessage response = null;
        try
        {
            var incoming = context.Request;
            request = new HttpRequestMessage(
                new HttpMethod(incoming.HttpMethod),
                "http://" + targetHost + ":" + targetPort + incoming.RawUrl);
            request.Headers.TryAddWithoutValidation("X-Forwarded-Proto", "https");
            if (!String.IsNullOrWhiteSpace(incoming.Headers["Host"]))
                request.Headers.TryAddWithoutValidation("X-Forwarded-Host", incoming.Headers["Host"]);

            foreach (var name in incoming.Headers.AllKeys)
            {
                if (HopByHop.Contains(name) || name.Equals("X-Forwarded-Proto", StringComparison.OrdinalIgnoreCase) || name.Equals("X-Forwarded-Host", StringComparison.OrdinalIgnoreCase))
                    continue;
                request.Headers.TryAddWithoutValidation(name, incoming.Headers[name]);
            }

            if (incoming.HasEntityBody)
            {
                if (incoming.ContentLength64 > MaxBodyBytes)
                    throw new InvalidOperationException("request_body_too_large");
                using (var memory = new MemoryStream())
                {
                    incoming.InputStream.CopyTo(memory);
                    if (memory.Length > MaxBodyBytes)
                        throw new InvalidOperationException("request_body_too_large");
                    request.Content = new ByteArrayContent(memory.ToArray());
                }
                if (!String.IsNullOrWhiteSpace(incoming.ContentType))
                    request.Content.Headers.TryAddWithoutValidation("Content-Type", incoming.ContentType);
            }

            // ResponseHeadersRead is required for /api/lite/events and other
            // bounded streaming reads. Buffering the response deadlocks later
            // browser calls and makes auth state appear to disappear.
            response = client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead).GetAwaiter().GetResult();
            context.Response.StatusCode = (int)response.StatusCode;
            CopyHeaders(response, context.Response);
            context.Response.KeepAlive = false;
            if (response.Content.Headers.ContentLength.HasValue)
                context.Response.ContentLength64 = response.Content.Headers.ContentLength.Value;
            else
                context.Response.SendChunked = true;
            using (var stream = response.Content.ReadAsStreamAsync().GetAwaiter().GetResult())
                stream.CopyTo(context.Response.OutputStream);
            context.Response.OutputStream.Flush();
        }
        catch
        {
            try
            {
                context.Response.StatusCode = 502;
                context.Response.ContentLength64 = 0;
            }
            catch { }
        }
        finally
        {
            try { context.Response.Close(); } catch { }
            if (response != null) response.Dispose();
            if (request != null) request.Dispose();
        }
    }

    private static void CopyHeaders(HttpResponseMessage response, HttpListenerResponse target)
    {
        var headers = response.Headers.Concat(response.Content.Headers);
        foreach (var header in headers)
        {
            if (header.Key.Equals("Set-Cookie", StringComparison.OrdinalIgnoreCase))
            {
                // Set-Cookie is not comma-combinable; preserve every value.
                foreach (var value in header.Value)
                    target.AppendHeader("Set-Cookie", value);
                continue;
            }
            if (HopByHop.Contains(header.Key)) continue;
            foreach (var value in header.Value)
                target.AppendHeader(header.Key, value);
        }
    }
}
'@

Add-Type -TypeDefinition $source -ReferencedAssemblies @('System.Net.Http.dll')
[PocketLabQualificationHttpsBridge]::Run($ListenPort, $TargetHost, $TargetPort, $MaxConcurrentRequests)
