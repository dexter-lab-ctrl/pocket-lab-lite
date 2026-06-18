import React, { useState } from 'react';
import { FileCode, Copy, Check } from 'lucide-react';

export default function CodeBlock({ code, id, filename = "bootstrap.sh" }) {
  const [copiedId, setCopiedId] = useState(null);

  const handleCopy = () => {
    if (navigator.vibrate) navigator.vibrate(10);
    const textArea = document.createElement("textarea");
    textArea.value = code;
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      // Legacy execCommand is preferred here to bypass restrictive iframe/sandbox clipboard policies
      document.execCommand('copy');
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2500);
    } catch (err) {
      console.error('Failed to copy text', err);
    }
    document.body.removeChild(textArea);
  };

  return (
    <div className="relative group mt-5 animate-in fade-in slide-in-from-bottom-2 duration-500">

      {/* Premium Mac-style Terminal Header */}
      <div className="flex items-center px-4 py-3 bg-[#0f1423] border border-white/5 border-b-0 rounded-t-2xl shadow-inner relative z-10">
        <div className="flex space-x-2">
          <div className="w-3 h-3 rounded-full bg-red-500/80 border border-red-500/50 shadow-sm transition-transform hover:scale-125 cursor-default"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-500/80 border border-yellow-500/50 shadow-sm transition-transform hover:scale-125 cursor-default"></div>
          <div className="w-3 h-3 rounded-full bg-green-500/80 border border-green-500/50 shadow-sm transition-transform hover:scale-125 cursor-default"></div>
        </div>
        <div className="mx-auto text-xs text-slate-400 font-mono flex items-center tracking-widest uppercase opacity-80">
          <FileCode className="w-3.5 h-3.5 mr-2 text-indigo-400" /> {filename}
        </div>
        <div className="w-12"></div>
      </div>

      {/* Scrollable Code Area */}
      <div className="relative bg-[#05080f] rounded-b-2xl border border-white/5 overflow-hidden shadow-[inset_0_0_30px_rgba(0,0,0,0.8)]">
        <pre className="p-6 overflow-x-auto text-[13px] font-mono leading-relaxed whitespace-pre-wrap text-slate-300 max-h-[500px] scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          {code}
        </pre>
      </div>

      {/* Floating Glassmorphic Copy Button */}
      <button
        onClick={handleCopy}
        className={`absolute top-14 right-4 p-2.5 rounded-xl border transition-all duration-300 shadow-xl flex items-center space-x-2 ${
          copiedId === id
            ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400 opacity-100'
            : 'bg-white/10 backdrop-blur-md border-white/10 text-slate-200 opacity-0 group-hover:opacity-100 hover:bg-indigo-600 hover:border-indigo-400'
        }`}
      >
        {copiedId === id ? (
          <><Check className="w-4 h-4" /> <span className="text-[10px] font-black uppercase tracking-widest pr-1">Copied</span></>
        ) : (
          <Copy className="w-4 h-4" />
        )}
      </button>
    </div>
  );
}
