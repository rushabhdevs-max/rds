"use client";

export function TypingIndicator() {
  return (
    <div className="mb-3 flex justify-start">
      <div className="mr-2 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-blue-600 text-xs font-semibold text-white">
        A
      </div>
      <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <div className="flex gap-1">
          <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]"></span>
          <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]"></span>
          <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]"></span>
        </div>
      </div>
    </div>
  );
}
