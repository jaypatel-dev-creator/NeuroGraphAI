import ToolCallBadge from '../ToolCall/ToolCallBadge'

export default function StreamingMessage({ message }) {
  return (
    <div className="flex flex-col gap-2">
      {/* Completed tool calls */}
      {message.toolCalls?.map((tc, idx) => (
        <ToolCallBadge key={idx} toolCall={tc} />
      ))}

      {/* Currently running tool */}
      {message.currentTool && (
        <ToolCallBadge toolCall={message.currentTool} />
      )}

      {/* Streaming text */}
      {message.content && (
        <div className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
          {message.content}
          <span className="inline-block w-1.5 h-4 bg-gray-400 ml-0.5 animate-pulse rounded-sm" />
        </div>
      )}

      {/* Thinking indicator when no content yet */}
      {!message.content && !message.currentTool && (
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      )}
    </div>
  )
}