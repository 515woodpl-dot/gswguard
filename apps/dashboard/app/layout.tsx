import type { Metadata } from 'next';

import './globals.css';

export const metadata: Metadata = {
  title: 'GSWGuard',
  description: 'Golden Stone Works endpoint management',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
