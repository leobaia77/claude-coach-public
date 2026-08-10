import { useCallback, useRef, useState } from 'react'
import { streamCoach } from './coachApi'

interface Msg {
  id: string
  role: 'user' | 'assistant'
  text: string
  tools?: string[]
}

export function ChatBox({
  kind,
  placeholder,
  seed,
}: {
  kind: 'chat' | 'onboarding' | 'weekly'
  placeholder?: string
  seed?: string
}) {
  const [messages, setMessages] = useState<Msg[]>(
    seed ? [{ id: 'seed', role: 'assistant', text: seed }] : [],
  )
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const sessionRef = useRef<string | undefined>(undefined)

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || streaming) return
      const stamp = Date.now()
      const aid = `a${stamp}`
      setMessages((m) => [
        ...m,
        { id: `u${stamp}`, role: 'user', text },
        { id: aid, role: 'assistant', text: '', tools: [] },
      ])
      setInput('')
      setStreaming(true)
      let acc = ''
      const patch = (fn: (m: Msg) => Msg) =>
        setMessages((ms) => ms.map((msg) => (msg.id === aid ? fn(msg) : msg)))

      await streamCoach(text, sessionRef.current, kind, {
        onText: (t) => {
          acc += t
          patch((m) => ({ ...m, text: acc }))
        },
        onTool: (name) => patch((m) => ({ ...m, tools: [...(m.tools ?? []), name] })),
        onDone: (sid) => {
          if (sid) sessionRef.current = sid
          if (!acc) patch((m) => ({ ...m, text: '(no response)' }))
          setStreaming(false)
        },
        onError: (err) => {
          patch((m) => ({ ...m, text: acc || `⚠️ ${err}` }))
          setStreaming(false)
        },
      })
    },
    [kind, streaming],
  )

  return (
    <div className="chatbox">
      <div className="chatbox-log">
        {messages.map((m) => (
          <div key={m.id} className={`msg msg-${m.role}`}>
            {m.tools && m.tools.length > 0 && (
              <div className="msg-tools">{m.tools.map((t) => `⚙ ${t}`).join('  ')}</div>
            )}
            <div className="msg-text">{m.text || (streaming ? '…' : '')}</div>
          </div>
        ))}
        {messages.length === 0 && <div className="chatbox-empty">Ask your coach anything.</div>}
      </div>
      <form
        className="chatbox-input"
        onSubmit={(e) => {
          e.preventDefault()
          void send(input)
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholder ?? 'Message your coach…'}
          disabled={streaming}
        />
        <button type="submit" disabled={streaming || !input.trim()}>
          {streaming ? '…' : 'Send'}
        </button>
      </form>
    </div>
  )
}
