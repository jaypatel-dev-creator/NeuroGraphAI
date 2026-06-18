import { useState } from 'react'
import { useChat } from '../../context/ChatContext'

export default function ChatInput({ disabled }) {
  const [input, setInput] = useState('')
  const { sendMessage } = useChat()

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    setInput('')
    await sendMessage(trimmed)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex items-end gap-2 border border-gray-200 rounded-2xl px-4 py-3 bg-white shadow-sm focus-within:border-gray-300 transition-colors">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Message NeuroGraph AI..."
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none bg-transparent outline-none text-sm text-gray-800 placeholder-gray-400 max-h-32 overflow-y-auto disabled:opacity-50"
        style={{ lineHeight: '1.5' }}
        onInput={(e) => {
          e.target.style.height = 'auto'
          e.target.style.height = Math.min(e.target.scrollHeight, 128) + 'px'
        }}
      />
      <button
        onClick={handleSend}
        disabled={disabled || !input.trim()}
        className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-gray-800 text-white disabled:opacity-30 hover:bg-gray-700 transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 19V5M5 12l7-7 7 7"/>
        </svg>
      </button>
    </div>
  )
}