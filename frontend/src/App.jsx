import { NavLink, Route, Routes } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_ADK_API_BASE_URL ?? "/api";
const ADK_APP_NAME = import.meta.env.VITE_ADK_APP_NAME ?? "root_agent";
const USER_STORAGE_KEY = "hanyang-study-agent-user-id";
const CURRENT_SESSION_ID = createSessionId();
const starterMessages = [
  {
    id: 1,
    role: "assistant",
    content: "안녕하세요. Google ADK 백엔드와 연결된 Hanyang Study Agent입니다.",
    meta: "방금 연결됨",
  },
];

const quickPrompts = [
  "운영체제 중간고사 대비 핵심 개념 정리해줘",
  "캡스톤 팀 미팅 전에 체크리스트 만들어줘",
  "이번 주 수업 기준으로 복습 루틴 추천해줘",
];

const sessions = [
  { id: "today", title: "데이터베이스 과제 플랜", updatedAt: "오늘 13:10" },
  { id: "exam", title: "알고리즘 시험 대비", updatedAt: "어제 19:40" },
  { id: "team", title: "캡스톤 발표 리허설", updatedAt: "3월 11일" },
];

const dashboardCards = [
  { label: "활성 세션", value: "03", hint: "최근 학습 대화" },
  { label: "추천 루틴", value: "12", hint: "과목별 자동 제안" },
  { label: "연결 예정", value: "Login", hint: "인증 로직 확장 가능" },
];

const THEME_STORAGE_KEY = "hanyang-study-agent-theme";

function createSessionId() {
  const nextId =
    window.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `web-session-${nextId}`;
}

function getOrCreateStoredId(storageKey, prefix) {
  const savedId = window.localStorage.getItem(storageKey);
  if (savedId) {
    return savedId;
  }

  const nextId =
    window.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const storedId = `${prefix}-${nextId}`;
  window.localStorage.setItem(storageKey, storedId);
  return storedId;
}

function getInitialTheme() {
  const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (savedTheme === "light" || savedTheme === "dark") {
    return savedTheme;
  }

  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

async function ensureAdkSession(userId, sessionId) {
  const response = await fetch(
    `${API_BASE_URL}/apps/${ADK_APP_NAME}/users/${userId}/sessions/${sessionId}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    }
  );

  if (response.ok) {
    return;
  }

  const errorText = await response.text();
  if (errorText.includes("Session already exists")) {
    return;
  }

  throw new Error(errorText || "ADK 세션을 만들지 못했습니다.");
}

function extractAgentText(events) {
  const eventList = Array.isArray(events) ? events : [events];

  for (const event of [...eventList].reverse()) {
    const parts = event?.content?.parts ?? event?.content?.Parts ?? [];
    const text = parts
      .map((part) => part?.text ?? part?.Text)
      .filter(Boolean)
      .join("\n")
      .trim();

    if (text) {
      return text;
    }
  }

  return "응답은 도착했지만 표시할 텍스트를 찾지 못했습니다.";
}

function parseJsonResponse(content) {
  const trimmed = content.trim();
  const jsonText = trimmed.startsWith("```json")
    ? trimmed.replace(/^```json\s*/i, "").replace(/```$/i, "").trim()
    : trimmed;

  if (!jsonText.startsWith("{") && !jsonText.startsWith("[")) {
    return null;
  }

  try {
    return JSON.parse(jsonText);
  } catch {
    return null;
  }
}

function parseEverytimeResponse(content) {
  if (!content.includes("Everytime") && !content.includes("에브리타임") && !content.includes("everytime.kr")) {
    return null;
  }

  const normalizeText = (value) =>
    value
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&")
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .trim();

  const groupPostsByBoard = (posts) => {
    const groupedBoards = [];

    for (const post of posts) {
      const title = post.boardTitle || "Everytime";
      let board = groupedBoards.find((item) => item.title === title);
      if (!board) {
        board = {
          title,
          url: post.boardUrl ?? post.url.replace(/\/v\/[^/]+$/, ""),
          posts: [],
        };
        groupedBoards.push(board);
      }

      board.posts.push(post);
    }

    return groupedBoards;
  };

  const boardPattern =
    /###\s+(.+?)\s+\(\[Link\]\((https?:\/\/[^)]+)\)\)([\s\S]*?)(?=\n---|\n###\s+|$)/g;
  const postPattern =
    /\d+\.\s+\*\*\[([^\]]+)\]\((https?:\/\/[^)]+)\)\*\*\s+Author:\s*(.*?)\s+Created at:\s*(.*?)\s+Preview:\s*([\s\S]*?)\s+Comments:\s*(\d+)\s+\|\s+Likes:\s*(\d+)/g;
  const boards = [];

  for (const boardMatch of content.matchAll(boardPattern)) {
    const [, title, url, body] = boardMatch;
    const posts = [];

    for (const postMatch of body.matchAll(postPattern)) {
      const [, postTitle, postUrl, author, createdAt, preview, comments, likes] = postMatch;
      posts.push({
        title: normalizeText(postTitle),
        url: postUrl,
        author: normalizeText(author),
        createdAt: normalizeText(createdAt),
        preview: normalizeText(preview.replace(/\n---[\s\S]*$/g, "")),
        comments,
        likes,
      });
    }

    boards.push({ title: normalizeText(title), url, posts });
  }

  if (boards.length) {
    return boards;
  }

  const flatPostPattern =
    /(?:^|\n)\s*\d+\.\s+(?:(.+?)\s+-\s+)?(?:\*\*)?\[([^\]]+)\]\((https?:\/\/[^)]+)\)(?:\*\*)?\s+Author:\s*(.*?)\s+Created at:\s*(.*?)\s+Preview:\s*([\s\S]*?)\s+Comments:\s*(\d+)\s*\|\s*Likes:\s*(\d+)/g;
  const flatPosts = [];

  for (const postMatch of content.matchAll(flatPostPattern)) {
    const [, boardTitle, postTitle, postUrl, author, createdAt, preview, comments, likes] = postMatch;
    flatPosts.push({
      boardTitle: normalizeText(boardTitle ?? "Everytime"),
      title: normalizeText(postTitle),
      url: postUrl,
      author: normalizeText(author),
      createdAt: normalizeText(createdAt),
      preview: normalizeText(preview),
      comments,
      likes,
    });
  }

  return flatPosts.length ? groupPostsByBoard(flatPosts) : null;
}

async function sendMessageToAgent(prompt) {
  const userId = getOrCreateStoredId(USER_STORAGE_KEY, "web-user");
  const sessionId = CURRENT_SESSION_ID;

  await ensureAdkSession(userId, sessionId);

  const response = await fetch(`${API_BASE_URL}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      appName: ADK_APP_NAME,
      userId,
      sessionId,
      newMessage: {
        role: "user",
        parts: [{ text: prompt }],
      },
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "ADK 응답을 받지 못했습니다.");
  }

  return extractAgentText(await response.json());
}

function renderInlineText(text) {
  const tokens = text.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)]+\)|https?:\/\/\S+)/g);

  return tokens.map((token, index) => {
    const linkMatch = token.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
    if (linkMatch) {
      return (
        <a key={`${token}-${index}`} href={linkMatch[2]} target="_blank" rel="noreferrer">
          {linkMatch[1]}
        </a>
      );
    }

    if (token.startsWith("http")) {
      return (
        <a key={`${token}-${index}`} href={token} target="_blank" rel="noreferrer">
          {token}
        </a>
      );
    }

    if (token.startsWith("**") && token.endsWith("**")) {
      return <strong key={`${token}-${index}`}>{token.slice(2, -2)}</strong>;
    }

    return token;
  });
}

function JsonResponse({ value }) {
  return (
    <pre className="json-response">
      <code>{JSON.stringify(value, null, 2)}</code>
    </pre>
  );
}

function EverytimeResponse({ boards }) {
  return (
    <div className="everytime-response">
      {boards.map((board) => (
        <section className="board-section" key={board.url}>
          <div className="board-header">
            <h3>{board.title}</h3>
            <a href={board.url} target="_blank" rel="noreferrer">
              게시판 열기
            </a>
          </div>
          <div className="post-grid">
            {board.posts.map((post) => (
              <article className="post-card" key={post.url}>
                <a className="post-title" href={post.url} target="_blank" rel="noreferrer">
                  {post.title}
                </a>
                <p>{post.preview}</p>
                <div className="post-meta">
                  <span>{post.author}</span>
                  <span>{post.createdAt}</span>
                  <span>댓글 {post.comments}</span>
                  <span>좋아요 {post.likes}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function TextResponse({ content }) {
  return (
    <div className="text-response">
      {content
        .split(/\n{2,}/)
        .map((paragraph) => paragraph.trim())
        .filter(Boolean)
        .map((paragraph, index) => {
          if (paragraph.startsWith("### ")) {
            return <h3 key={`${paragraph}-${index}`}>{renderInlineText(paragraph.slice(4))}</h3>;
          }

          if (paragraph.startsWith("- ") || /^\d+\.\s/.test(paragraph)) {
            return <p key={`${paragraph}-${index}`}>{renderInlineText(paragraph)}</p>;
          }

          return <p key={`${paragraph}-${index}`}>{renderInlineText(paragraph)}</p>;
        })}
    </div>
  );
}

function MessageContent({ content, role }) {
  if (role === "user") {
    return <p className="message-text">{content}</p>;
  }

  const jsonValue = parseJsonResponse(content);
  if (jsonValue) {
    return <JsonResponse value={jsonValue} />;
  }

  const everytimeBoards = parseEverytimeResponse(content);
  if (everytimeBoards) {
    return <EverytimeResponse boards={everytimeBoards} />;
  }

  return <TextResponse content={content} />;
}

function App() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  return (
    <div className="app-shell">
      <div className="background-orb orb-left" />
      <div className="background-orb orb-right" />
      <header className="topbar">
        <div>
          <p className="eyebrow">Hanyang University</p>
          <h1>Hanyang Study Agent</h1>
        </div>
        <div className="topbar-actions">
          <nav className="topnav">
            <NavLink to="/" end>
              Chat Demo
            </NavLink>
            <NavLink to="/login">Login</NavLink>
            <NavLink to="/mypage">My Page</NavLink>
          </nav>
          <button
            className="theme-toggle"
            type="button"
            onClick={() => setTheme((currentTheme) => (currentTheme === "dark" ? "light" : "dark"))}
            aria-label={theme === "dark" ? "화이트 모드로 전환" : "다크 모드로 전환"}
          >
            <span>{theme === "dark" ? "Light" : "Dark"}</span>
            <strong>{theme === "dark" ? "화이트 모드" : "다크 모드"}</strong>
          </button>
        </div>
      </header>

      <Routes>
        <Route path="/" element={<ChatDemoPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/mypage" element={<MyPage />} />
      </Routes>
    </div>
  );
}

function ChatDemoPage() {
  const [messages, setMessages] = useState(starterMessages);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const stats = useMemo(
    () => ({
      totalMessages: messages.length,
      userMessages: messages.filter((message) => message.role === "user").length,
    }),
    [messages]
  );

  const handleSend = async (nextPrompt) => {
    const prompt = (nextPrompt ?? input).trim();
    if (!prompt || isSending) {
      return;
    }

    setErrorMessage("");
    setIsSending(true);

    const userMessage = {
      id: Date.now(),
      role: "user",
      content: prompt,
      meta: "직접 입력",
    };

    setMessages((current) => [...current, userMessage]);
    setInput("");

    try {
      const answer = await sendMessageToAgent(prompt);
      const assistantMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: answer,
        meta: "ADK 응답",
      };

      setMessages((current) => [...current, assistantMessage]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
      setErrorMessage(message);
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: "백엔드 응답을 받지 못했습니다. 서버 상태와 API 설정을 확인해주세요.",
          meta: "연결 오류",
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <main className="page-grid">
      <aside className="panel sidebar">
        <section>
          <p className="section-label">Overview</p>
          <h2>Demo Workspace</h2>
          <p className="muted">
            프론트는 Docker Compose의 Google ADK API 서버로 질문을 보내고, 루트
            에이전트가 만든 응답을 이 화면에 표시합니다.
          </p>
        </section>

        <section className="card-grid">
          {dashboardCards.map((card) => (
            <article className="mini-card" key={card.label}>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <small>{card.hint}</small>
            </article>
          ))}
        </section>

        <section>
          <div className="section-header">
            <p className="section-label">Recent Sessions</p>
            <span>{sessions.length} items</span>
          </div>
          <div className="session-list">
            {sessions.map((session) => (
              <button className="session-item" key={session.id} type="button">
                <strong>{session.title}</strong>
                <span>{session.updatedAt}</span>
              </button>
            ))}
          </div>
        </section>
      </aside>

      <section className="panel hero-panel">
        <div className="hero-copy">
          <p className="section-label">Chatbot Demo</p>
          <h2>학습 질문, 일정 정리, 시험 대비를 한 화면에서</h2>
          <p className="muted">
            빠른 질문 버튼이나 직접 입력으로 Google ADK 백엔드에 메시지를 보내고,
            응답을 같은 대화창에서 확인할 수 있습니다.
          </p>
        </div>

        <div className="quick-prompt-row">
          {quickPrompts.map((prompt) => (
            <button key={prompt} type="button" onClick={() => handleSend(prompt)} disabled={isSending}>
              {prompt}
            </button>
          ))}
        </div>

        <div className="chat-window">
          <div className="chat-meta">
            <span>Total {stats.totalMessages}</span>
            <span>User {stats.userMessages}</span>
            <span>Assistant {stats.totalMessages - stats.userMessages}</span>
          </div>

          <div className="message-list">
            {messages.map((message) => (
              <article
                key={message.id}
                className={`message-bubble ${message.role === "user" ? "user" : "assistant"}`}
              >
                <span className="message-role">
                  {message.role === "user" ? "You" : "Agent"}
                </span>
                <MessageContent content={message.content} role={message.role} />
                <small>{message.meta}</small>
              </article>
            ))}
            {isSending ? (
              <article className="message-bubble assistant">
                <span className="message-role">Agent</span>
                <p>응답을 생성하는 중입니다...</p>
                <small>ADK 처리 중</small>
              </article>
            ) : null}
          </div>

          {errorMessage ? <p className="error-message">{errorMessage}</p> : null}

          <div className="composer">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
              placeholder="예: 이번 주 머신러닝 발표 준비 순서를 정리해줘"
              rows={3}
              disabled={isSending}
            />
            <button type="button" onClick={() => handleSend()} disabled={isSending}>
              {isSending ? "Sending..." : "Send Message"}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}

function LoginPage() {
  return (
    <main className="single-panel-page">
      <section className="panel placeholder-page">
        <p className="section-label">Future Auth</p>
        <h2>로그인 영역 placeholder</h2>
        <p className="muted">
          추후 소셜 로그인 또는 학교 계정 인증을 붙일 수 있도록 별도 라우트로 분리했습니다.
        </p>
        <div className="placeholder-grid">
          <article>
            <strong>예정 기능</strong>
            <span>이메일/소셜 로그인</span>
          </article>
          <article>
            <strong>상태 저장</strong>
            <span>토큰, 세션, 보호 라우트</span>
          </article>
        </div>
      </section>
    </main>
  );
}

function MyPage() {
  return (
    <main className="single-panel-page">
      <section className="panel placeholder-page">
        <p className="section-label">Future Dashboard</p>
        <h2>마이페이지 영역 placeholder</h2>
        <p className="muted">
          학습 통계, 최근 대화, 즐겨찾기 자료를 붙일 공간입니다. 현재는 데모 카드만
          배치했습니다.
        </p>
        <div className="placeholder-grid">
          <article>
            <strong>학습 리포트</strong>
            <span>주간 질문 수, 과목별 활동량</span>
          </article>
          <article>
            <strong>저장 콘텐츠</strong>
            <span>북마크한 요약, 루틴, 일정</span>
          </article>
          <article>
            <strong>설정</strong>
            <span>프로필, 알림, 계정 관리</span>
          </article>
        </div>
      </section>
    </main>
  );
}

export default App;
