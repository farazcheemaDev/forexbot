export default function Login({ searchParams }) {
  return (
    <main className="login">
      <div className="panel">
        <h1>Forexbot Live</h1>
        <p className="sub">Paper books on the VM - read-only.</p>
        <form method="post" action="/api/login">
          <input type="password" name="password" placeholder="Password" autoComplete="current-password" required />
          <div style={{ height: 10 }} />
          <button type="submit">Sign in</button>
        </form>
        {searchParams?.e ? <p className="down">Wrong password, or the dashboard is not configured.</p> : null}
      </div>
    </main>
  );
}
