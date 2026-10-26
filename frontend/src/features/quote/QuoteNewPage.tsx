import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function QuoteNewPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [categoryId] = useState(1);
  const [address, setAddress] = useState("");
  const [isUrgent, setIsUrgent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api("/quotes/requests", {
        method: "POST",
        body: JSON.stringify({ title, category_id: categoryId, address, is_urgent: isUrgent }),
      });
      navigate("/quote/mine");
    } catch (err: any) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-md space-y-3 p-4">
      <h1 className="text-xl font-bold">درخواست استعلام</h1>
      <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="شرح کار" />
      <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="آدرس" />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={isUrgent} onChange={(e) => setIsUrgent(e.target.checked)} />
        فوری (۲ ساعت)
      </label>
      <Button disabled={loading} type="submit">ثبت درخواست</Button>
      {error && <p className="text-sm text-rose-600">{error}</p>}
    </form>
  );
}
