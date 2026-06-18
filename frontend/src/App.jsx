import { ChatProvider } from './context/ChatContext'
import ChatPage from './pages/ChatPage'

export default function App() {
  return (
    <ChatProvider>
      <ChatPage />
    </ChatProvider>
  )
}