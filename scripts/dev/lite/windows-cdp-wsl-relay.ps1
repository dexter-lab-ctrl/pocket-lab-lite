[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$WslAddress,
  [string]$WindowsAddress = '172.19.0.1',
  [int]$ChannelPort = 19223,
  [string]$TargetAddress = '127.0.0.1',
  [int]$TargetPort = 9222,
  [int]$ChannelCount = 12
)

$ErrorActionPreference = 'Stop'

if ($WindowsAddress -ne '172.19.0.1' -or $ChannelPort -ne 19223 -or $TargetAddress -ne '127.0.0.1' -or $TargetPort -ne 9222 -or $ChannelCount -ne 12) {
  throw 'This relay is fixed to the WSL private channel and the existing localhost Android CDP endpoint.'
}
if ($WslAddress -notmatch '^172\.19\.(?:\d{1,3})\.(?:\d{1,3})$') {
  throw 'The relay WSL address must be on the private 172.19/20 WSL interface.'
}

Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Net.Sockets;
using System.Threading.Tasks;

public static class PocketLabCdpReverseRelay
{
    private static readonly byte[] Hello = new byte[] { 0x50, 0x4C, 0x52, 0x31 };
    private static readonly byte[] Use = new byte[] { 0x55, 0x53, 0x45, 0x31 };

    private static async Task<byte[]> ReadExact(NetworkStream stream, int count)
    {
        var buffer = new byte[count];
        var offset = 0;
        while (offset < count)
        {
            var read = await stream.ReadAsync(buffer, offset, count - offset).ConfigureAwait(false);
            if (read <= 0) throw new IOException("relay_channel_closed");
            offset += read;
        }
        return buffer;
    }

    private static bool Equal(byte[] left, byte[] right)
    {
        if (left.Length != right.Length) return false;
        for (var index = 0; index < left.Length; index++)
        {
            if (left[index] != right[index]) return false;
        }
        return true;
    }

    private static async Task Copy(Stream source, Stream destination)
    {
        var buffer = new byte[64 * 1024];
        try
        {
            int read;
            while ((read = await source.ReadAsync(buffer, 0, buffer.Length).ConfigureAwait(false)) > 0)
            {
                await destination.WriteAsync(buffer, 0, read).ConfigureAwait(false);
                await destination.FlushAsync().ConfigureAwait(false);
            }
        }
        catch (IOException) { }
        catch (SocketException) { }
    }

    private static async Task Maintain(string wslAddress, int channelPort, string targetAddress, int targetPort)
    {
        while (true)
        {
            try
            {
                using (var relay = new TcpClient())
                {
                    await relay.ConnectAsync(wslAddress, channelPort).ConfigureAwait(false);
                    using (var relayStream = relay.GetStream())
                    {
                        await relayStream.WriteAsync(Hello, 0, Hello.Length).ConfigureAwait(false);
                        await relayStream.FlushAsync().ConfigureAwait(false);
                        var response = await ReadExact(relayStream, Use.Length).ConfigureAwait(false);
                        if (!Equal(response, Use)) throw new IOException("relay_channel_not_assigned");
                        using (var target = new TcpClient())
                        {
                            await target.ConnectAsync(targetAddress, targetPort).ConfigureAwait(false);
                            using (var targetStream = target.GetStream())
                            {
                                var upstream = Copy(relayStream, targetStream);
                                var downstream = Copy(targetStream, relayStream);
                                await Task.WhenAny(upstream, downstream).ConfigureAwait(false);
                            }
                        }
                    }
                }
            }
            catch (SocketException) { }
            catch (IOException) { }
            catch (ObjectDisposedException) { }
            await Task.Delay(250).ConfigureAwait(false);
        }
    }

    public static void Run(string wslAddress, int channelPort, string targetAddress, int targetPort, int channelCount)
    {
        Console.WriteLine("Pocket Lab standard-user reverse CDP relay connecting to WSL " + wslAddress + ":" + channelPort);
        var tasks = new Task[channelCount];
        for (var index = 0; index < channelCount; index++)
        {
            tasks[index] = Task.Run(() => Maintain(wslAddress, channelPort, targetAddress, targetPort));
        }
        Task.WaitAll(tasks);
    }
}
'@

[PocketLabCdpReverseRelay]::Run($WslAddress, $ChannelPort, $TargetAddress, $TargetPort, $ChannelCount)
