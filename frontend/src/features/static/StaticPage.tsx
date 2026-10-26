import { useParams } from "react-router-dom";

const CONTENT: Record<string, { title: string; body: string }> = {
  about: { title: "درباره نومکس", body: "نومکس بازار خدمات و کسب‌وکارهای محلی بهبهان است." },
  contact: { title: "تماس با ما", body: "برای پشتیبانی از طریق پنل کاربری پیام دهید." },
};

export default function StaticPage() {
  const { page } = useParams<{ page: string }>();
  const content = CONTENT[page ?? ""] ?? { title: "یافت نشد", body: "" };
  return (
    <main className="mx-auto max-w-xl p-4 space-y-3">
      <h1 className="text-xl font-bold">{content.title}</h1>
      <p className="text-slate-600">{content.body}</p>
    </main>
  );
}
