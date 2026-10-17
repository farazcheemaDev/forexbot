export default function Login({ searchParams }) {
  return (
    <main className="login">
      <div className="card">
        <h1><span className="brand"><i>F</i></span>Forexbot</h1>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>Paper trading, live. Read-only.</p>
        <form method="post" action="/api/login">
          <input type="password" name="password" placeholder="Password" autoComplete="current-password" required />
          <button type="submit">Sign in</button>
        </form>
        {searchParams?.e ? <p className="down" style={{ fontSize: 13 }}>Wrong password, or the dashboard is not configured.</p> : null}
      </div>
    </main>
  );
}
