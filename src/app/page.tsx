import { ChatWindow } from "@/components/ChatWindow";

export default function Home() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-100 via-indigo-50 to-blue-100 p-0 md:p-6">
      <ChatWindow />
    </div>
  );
}
