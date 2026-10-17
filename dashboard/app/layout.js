import "./globals.css";

export const metadata = { title: "Forexbot Live", description: "The final machine's paper books, live" };
export const viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
