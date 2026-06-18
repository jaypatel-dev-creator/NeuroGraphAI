import { useChat } from '../../context/ChatContext'
import ThreadList from './ThreadList'

export default function Sidebar() {
  const { createThread, setShowProfile, showProfile, loadProfile } = useChat()

  const handleNewChat = async () => {
    await createThread()
  }

  const handleToggleProfile = async () => {
    if (!showProfile) await loadProfile()
    setShowProfile(!showProfile)
  }

  return (
    <aside className="w-64 flex flex-col border-r border-gray-100 bg-gray-50 h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-100">
        <h1 className="text-base font-semibold text-gray-800 tracking-tight">
          NeuroGraph AI
        </h1>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
        >
          <span className="text-lg leading-none">+</span>
          New Chat
        </button>
      </div>

      {/* Thread List */}
      <div className="flex-1 overflow-y-auto">
        <ThreadList />
      </div>

      {/* Profile Toggle */}
      <div className="p-3 border-t border-gray-100">
        <button
          onClick={handleToggleProfile}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
            showProfile
              ? 'bg-gray-200 text-gray-800'
              : 'text-gray-600 hover:bg-gray-200'
          }`}
        >
          <span>🧠</span>
          Memory Profile
        </button>
      </div>
    </aside>
  )
}