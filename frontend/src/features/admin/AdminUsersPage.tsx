import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge, RoleBadge } from "@/components/ui/badge";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button, Spinner } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { formatPhone, GROUP_LABELS, permissionLabel, ROLE_LABELS } from "@/lib/format";
import { formatJalali } from "@/lib/jalali";
import { useAuth } from "@/stores/auth";
import type { AdminUser, PermissionItem, Role } from "@/types";

const ROLES: Role[] = ["customer", "owner", "admin", "superadmin"];

function sameSet(first: string[], second: string[]): boolean {
  if (first.length !== second.length) return false;
  const set = new Set(first);
  return second.every((item) => set.has(item));
}

export function AdminUsersPage() {
  const me = useAuth((state) => state.user);
  const toast = useToast();

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [permissions, setPermissions] = useState<PermissionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [role, setRole] = useState<Role>("customer");
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [userResult, permissionResult] = await Promise.all([
        api<{ items: AdminUser[] }>("/admin/users"),
        api<{ items: PermissionItem[] }>("/admin/permissions"),
      ]);
      setUsers(userResult.items);
      setPermissions(permissionResult.items);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const groupedPermissions = useMemo(() => {
    const groups = new Map<string, PermissionItem[]>();
    for (const item of permissions) {
      const list = groups.get(item.group) ?? [];
      list.push(item);
      groups.set(item.group, list);
    }
    return [...groups.entries()].sort(([first], [second]) => first.localeCompare(second));
  }, [permissions]);

  function openEditor(user: AdminUser) {
    setEditing(user);
    setRole(user.role);
    setSelected(user.permissions);
  }

  function togglePermission(code: string) {
    setSelected((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    );
  }

  async function save() {
    if (!editing) return;
    const roleChanged = editing.role !== role;
    const permissionsChanged = role === "admin" && !sameSet(editing.permissions, selected);

    if (!roleChanged && !permissionsChanged) {
      setEditing(null);
      return;
    }

    setSaving(true);
    try {
      if (roleChanged) {
        await api(`/admin/users/${editing.id}/role`, {
          method: "PATCH",
          body: JSON.stringify({ role }),
        });
      }
      if (permissionsChanged) {
        await api(`/admin/users/${editing.id}/permissions`, {
          method: "PATCH",
          body: JSON.stringify({ permissions: selected }),
        });
      }
      toast("تغییرات کاربر ذخیره شد.");
      setEditing(null);
      await load();
    } catch (saveError) {
      toast(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">کاربران</h1>
          <p className="mt-1 text-xs text-slate-500">
            نقش و دسترسی‌های هر کاربر را مدیریت کنید. هر تغییر در گزارش رویدادها ثبت می‌شود.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={() => void load()} disabled={loading}>
          به‌روزرسانی
        </Button>
      </header>

      {loading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}

      {!loading && error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
          <p>{error}</p>
          <Button size="sm" variant="outline" className="mt-3" onClick={() => void load()}>
            تلاش دوباره
          </Button>
        </div>
      )}

      {!loading && !error && (
        <div className="space-y-3">
          {users.map((user) => (
            <article
              key={user.id}
              className="rounded-2xl border border-slate-200 bg-white p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-bold text-slate-900">
                    {user.full_name || "بدون نام"}
                    {user.id === me?.id && (
                      <span className="mr-2 text-[11px] font-normal text-brand-600">(شما)</span>
                    )}
                  </p>
                  <p className="mt-1 text-xs text-slate-500" dir="ltr">
                    {formatPhone(user.phone)}
                  </p>
                </div>
                <RoleBadge role={user.role} label={ROLE_LABELS[user.role]} />
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Badge tone={user.role === "admin" ? "amber" : "slate"}>
                  {user.role === "admin"
                    ? `${user.permissions.length} دسترسی`
                    : user.role === "superadmin"
                      ? "دسترسی کامل"
                      : "بدون دسترسی مدیریتی"}
                </Badge>
                {user.created_at && (
                  <span className="text-[11px] text-slate-400">
                    عضویت: {formatJalali(user.created_at)}
                  </span>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="mr-auto"
                  onClick={() => openEditor(user)}
                >
                  ویرایش
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}

      <BottomSheet
        open={editing !== null}
        title={editing ? `ویرایش ${editing.full_name || formatPhone(editing.phone)}` : "ویرایش کاربر"}
        onClose={() => setEditing(null)}
      >
        {editing && (
          <div className="space-y-5">
            <div>
              <label htmlFor="admin-role" className="mb-2 block text-sm font-medium text-slate-700">
                نقش
              </label>
              <select
                id="admin-role"
                value={role}
                disabled={editing.id === me?.id || saving}
                onChange={(event) => setRole(event.target.value as Role)}
                className="h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:bg-slate-50 disabled:text-slate-400"
              >
                {ROLES.map((item) => (
                  <option key={item} value={item}>
                    {ROLE_LABELS[item]}
                  </option>
                ))}
              </select>
              {editing.id === me?.id && (
                <p className="mt-2 text-xs text-amber-700">
                  نقش حساب خودتان قابل تغییر نیست تا دسترسی مدیریتی قطع نشود.
                </p>
              )}
            </div>

            {role === "admin" ? (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-700">دسترسی‌ها</p>
                  <button
                    type="button"
                    className="text-xs text-brand-600"
                    onClick={() => setSelected([])}
                  >
                    پاک کردن همه
                  </button>
                </div>
                <div className="max-h-[45dvh] space-y-4 overflow-y-auto rounded-2xl border border-slate-200 bg-slate-50/60 p-3">
                  {groupedPermissions.map(([group, items]) => (
                    <div key={group}>
                      <p className="mb-2 text-[11px] font-bold text-slate-400">
                        {GROUP_LABELS[group] ?? group}
                      </p>
                      <div className="grid gap-1.5">
                        {items.map((item) => {
                          const checked = selected.includes(item.code);
                          return (
                            <label
                              key={item.code}
                              className="flex cursor-pointer items-center gap-3 rounded-xl bg-white px-3 py-2 text-sm text-slate-700"
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => togglePermission(item.code)}
                                className="h-4 w-4 accent-brand-600"
                              />
                              <span>{permissionLabel(item.code)}</span>
                              <span className="mr-auto text-[10px] text-slate-300" dir="ltr">
                                {item.code}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="rounded-xl bg-slate-50 px-4 py-3 text-xs leading-6 text-slate-500">
                دسترسی‌های دقیق فقط برای نقش «مدیر» معنا دارد. نقش‌های مشتری، کسب‌وکار و
                مدیر کل از قواعد ثابت خودشان پیروی می‌کنند.
              </p>
            )}

            <div className="flex gap-2">
              <Button className="flex-1" loading={saving} onClick={() => void save()}>
                ذخیره تغییرات
              </Button>
              <Button variant="ghost" disabled={saving} onClick={() => setEditing(null)}>
                انصراف
              </Button>
            </div>
          </div>
        )}
      </BottomSheet>
    </section>
  );
}
