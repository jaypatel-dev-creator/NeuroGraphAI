import { useRef, useEffect } from 'react'
import { useChat } from '../../context/ChatContext'
import MessageBubble from './MessageBubble'
import StreamingMessage from './StreamingMessage'
import ChatInput from './ChatInput'

export default function ChatWindow() {
  const { messages, streamingMessage, activeThreadId, isStreaming, memoryNotification } = useChat()
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingMessage?.content])

  if (!activeThreadId) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-2xl font-semibold text-gray-800 mb-2">
            NeuroGraph AI
          </p>
          <p className="text-sm text-gray-400">
            Start a new conversation or select an existing one
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {messages.length === 0 && !streamingMessage && (
            <div className="text-center py-12">
              <p className="text-sm text-gray-400">
                Send a message to start the conversation
              </p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <MessageBubble key={idx} message={msg} />
          ))}

          {streamingMessage && (
            <StreamingMessage message={streamingMessage} />
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Memory update notification — fixed at bottom above input */}
      {memoryNotification && (
        <div className="px-4 pb-2">
          <div className="max-w-2xl mx-auto">
            <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-purple-50 border border-purple-100 text-xs text-purple-600">
              <span>🧠</span>
              <span>
                Memory updated: <span className="font-medium">{memoryNotification.keys.join(', ')}</span>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-gray-100 px-4 py-4">
        <div className="max-w-2xl mx-auto">
          <ChatInput disabled={isStreaming} />
        </div>
      </div>
    </div>
  )
}