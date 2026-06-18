import { createContext, useContext, useState, useCallback, useRef } from 'react'
import client from '../api/client'

const ChatContext = createContext(null)

export function ChatProvider({ children }) {
  const [threads, setThreads] = useState([])
  const [activeThreadId, setActiveThreadId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingMessage, setStreamingMessage] = useState(null)
  const [profile, setProfile] = useState([])
  const [showProfile, setShowProfile] = useState(false)

  // ref to prevent duplicate done events
  const doneCommittedRef = useRef(false)

  // --- Thread actions ---

  const loadThreads = useCallback(async () => {
    try {
      const res = await client.get('/threads')
      setThreads(res.data)
    } catch (err) {
      console.error('Failed to load threads:', err)
    }
  }, [])

  const createThread = useCallback(async () => {
    try {
      const res = await client.post('/threads', { title: 'New Chat' })
      setThreads((prev) => [res.data, ...prev])
      setActiveThreadId(res.data.id)
      setMessages([])
      return res.data
    } catch (err) {
      console.error('Failed to create thread:', err)
    }
  }, [])

  const selectThread = useCallback(async (threadId) => {
    setActiveThreadId(threadId)
    setMessages([])
    setStreamingMessage(null)
    try {
      const res = await client.get(`/chat/history/${threadId}`)
      setMessages(res.data.messages || [])
    } catch (err) {
      console.error('Failed to load history:', err)
    }
  }, [])

  const renameThread = useCallback(async (threadId, title) => {
    try {
      await client.patch(`/threads/${threadId}`, { title })
      setThreads((prev) =>
        prev.map((t) => (t.id === threadId ? { ...t, title, is_titled: true } : t))
      )
    } catch (err) {
      console.error('Failed to rename thread:', err)
    }
  }, [])

  const deleteThread = useCallback(async (threadId) => {
    try {
      await client.delete(`/threads/${threadId}`)
      setThreads((prev) => prev.filter((t) => t.id !== threadId))
      if (activeThreadId === threadId) {
        setActiveThreadId(null)
        setMessages([])
      }
    } catch (err) {
      console.error('Failed to delete thread:', err)
    }
  }, [activeThreadId])

  // --- Chat actions ---

  const sendMessage = useCallback(async (message) => {
    if (!activeThreadId || !message.trim()) return

    const humanMsg = { role: 'human', content: message }
    setMessages((prev) => [...prev, humanMsg])
    setIsStreaming(true)
    doneCommittedRef.current = false
    setStreamingMessage({
      role: 'ai',
      content: '',
      toolCalls: [],
      currentTool: null,
    })

    try {
      const response = await fetch('http://localhost:8000/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: activeThreadId, message }),
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            handleSSEEvent(event)
          } catch {
            // skip malformed lines
          }
        }
      }
    } catch (err) {
      console.error('Stream error:', err)
      setStreamingMessage(null)
      setIsStreaming(false)
    }
  }, [activeThreadId])

  const handleSSEEvent = useCallback((event) => {
    switch (event.type) {
      case 'text':
        setStreamingMessage((prev) => {
          if (!prev) return prev
          return { ...prev, content: prev.content + event.content }
        })
        break

      case 'tool_start':
        setStreamingMessage((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            currentTool: {
              tool_name: event.tool_name,
              tool_input: event.tool_input,
              tool_output: null,
              sources: [],
              status: 'running',
            },
          }
        })
        break

      case 'tool_end':
        setStreamingMessage((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            toolCalls: [
              ...prev.toolCalls,
              {
                tool_name: event.tool_name,
                tool_input: prev.currentTool?.tool_input || {},
                tool_output: event.tool_output,
                sources: event.sources || [],
                status: 'done',
              },
            ],
            currentTool: null,
          }
        })
        break

      case 'done':
        // guard against duplicate done events from StrictMode or stream quirks
        if (doneCommittedRef.current) break
        doneCommittedRef.current = true

        setStreamingMessage((prev) => {
          if (prev) {
            setMessages((msgs) => {
              const last = msgs[msgs.length - 1]
              if (last && last.role === 'ai' && last.content === prev.content) {
                return msgs
              }
              return [...msgs, { ...prev, currentTool: null }]
            })
          }
          return null
        })
        setIsStreaming(false)
        refreshThreadTitle(activeThreadId)
        break

      case 'error':
        setStreamingMessage((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            content: prev.content || 'Something went wrong. Please try again.',
          }
        })
        setIsStreaming(false)
        break

      default:
        break
    }
  }, [activeThreadId])

  const refreshThreadTitle = useCallback(async (threadId) => {
    if (!threadId) return
    try {
      const res = await client.get(`/threads/${threadId}`)
      setThreads((prev) =>
        prev.map((t) => (t.id === threadId ? res.data : t))
      )
    } catch {
      // non-critical
    }
  }, [])

  // --- Profile actions ---

  const loadProfile = useCallback(async () => {
    try {
      const res = await client.get('/memory/profile')
      setProfile(res.data.entries || [])
    } catch (err) {
      console.error('Failed to load profile:', err)
    }
  }, [])

  const deleteProfileEntry = useCallback(async (key) => {
    try {
      await client.delete(`/memory/profile/${key}`)
      setProfile((prev) => prev.filter((e) => e.key !== key))
    } catch (err) {
      console.error('Failed to delete profile entry:', err)
    }
  }, [])

  const clearProfile = useCallback(async () => {
    try {
      await client.delete('/memory/profile')
      setProfile([])
    } catch (err) {
      console.error('Failed to clear profile:', err)
    }
  }, [])

  return (
    <ChatContext.Provider value={{
      threads,
      activeThreadId,
      messages,
      isStreaming,
      streamingMessage,
      profile,
      showProfile,
      loadThreads,
      createThread,
      selectThread,
      renameThread,
      deleteThread,
      sendMessage,
      loadProfile,
      deleteProfileEntry,
      clearProfile,
      setShowProfile,
    }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used within ChatProvider')
  return ctx
}