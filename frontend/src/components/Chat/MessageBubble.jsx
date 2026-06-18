import ToolCallBadge from '../ToolCall/ToolCallBadge'

export default function MessageBubble({ message }) {
  const isHuman = message.role === 'human'

  if (isHuman) {
    return (
      <div className="flex justify-end">
        <div className="max-w-lg bg-gray-100 rounded-2xl px-4 py-3 text-sm text-gray-800">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Tool calls */}
      {message.toolCalls?.map((tc, idx) => (
        <ToolCallBadge key={idx} toolCall={tc} />
      ))}

      {/* AI response */}
      {message.content && (
        <div className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
          {message.content}
        </div>
      )}
    </div>
  )
}