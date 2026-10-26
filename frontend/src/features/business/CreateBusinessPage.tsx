import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function CreateBusinessPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [categoryId] = useState(1);
  const [address, setAddress] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api<{ data: { slug: string } }>("/businesses", {
        method: "POST",
        body: JSON.stringify({ name, category_id: categoryId, address }),
      });
      navigate(`/businesses/${res.data.slug}`);
    } catch (err: any) {
      setError(err?.message ?? "failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="max-w-md mx-auto p-4 space-y-3">
      <h1 className="text-xl font-bold">ثبت کسب‌وکار</h1>
      <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="نام" />
      <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="آدرس" />
      <Button disabled={loading} type="submit">ثبت</Button>
      {error && <p className="text-red-500 text-sm">{error}</p>}
    </form>
  );
}
