const TOOL_ICONS = {
  calculator: '🧮',
  weather: '🌤️',
  finance: '📈',
  get_datetime: '🕐',
  tavily_search: '🔍',
}

const TOOL_LABELS = {
  calculator: 'Calculator',
  weather: 'Weather',
  finance: 'Finance',
  get_datetime: 'Date & Time',
  tavily_search: 'Web Search',
}

export default function ToolCallBadge({ toolCall }) {
  const icon = TOOL_ICONS[toolCall.tool_name] || '🔧'
  const label = TOOL_LABELS[toolCall.tool_name] || toolCall.tool_name
  const isRunning = toolCall.status === 'running'

  return (
    <div className="inline-flex flex-col gap-1.5 max-w-lg">

      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${isRunning ? 'bg-blue-50 border-blue-100 text-blue-600' : 'bg-gray-50 border-gray-100 text-gray-600'}`}>
        <span>{icon}</span>
        <span>{isRunning ? `Using ${label}...` : `Used ${label}`}</span>
        {isRunning && <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />}
      </div>

      {toolCall.tool_output && !isRunning && (
        <div className="text-xs text-gray-500 px-3 py-2 bg-gray-50 rounded-xl border border-gray-100 max-w-lg">
          {toolCall.tool_output.length > 200 ? toolCall.tool_output.slice(0, 200) + '...' : toolCall.tool_output}
        </div>
      )}

      {toolCall.sources && toolCall.sources.length > 0 && (
        <div className="flex flex-col gap-1 px-1">
          {toolCall.sources.map((source, idx) => (
            <a key={idx} href={source.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:text-blue-700 hover:underline truncate max-w-sm">
              {source.title || source.url}
            </a>
          ))}
        </div>
      )}

    </div>
  )
}