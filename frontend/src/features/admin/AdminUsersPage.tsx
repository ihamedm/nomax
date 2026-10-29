import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge, RoleBadge } from "@/components/ui/badge";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { formatPhone, GROUP_LABELS, permissionLabel, ROLE_LABELS } from "@/lib/format";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";
import { DataTable, type DataColumn } from "@/features/admin/data-table";
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
  const queryClient = useQueryClient();

  const usersQuery = useApi<{ items: AdminUser[] }>(["admin", "users"], "/admin/users");
  const permissionsQuery = useApi<{ items: PermissionItem[] }>(
    ["admin", "permissions"],
    "/admin/permissions",
  );
  const users = usersQuery.data?.items ?? [];
  const permissions = permissionsQuery.data?.items ?? [];
  const loading = usersQuery.isLoading || permissionsQuery.isLoading;
  const error = usersQuery.error
    ? errorMessage(usersQuery.error)
    : permissionsQuery.error
      ? errorMessage(permissionsQuery.error)
      : null;

  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [role, setRole] = useState<Role>("customer");
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [newPhone, setNewPhone] = useState("");
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [roleFilter, setRoleFilter] = useState<"all" | Role>("all");
  const filteredUsers =
    roleFilter === "all" ? users : users.filter((user) => user.role === roleFilter);

  function reload() {
    void usersQuery.refetch();
    void permissionsQuery.refetch();
  }

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
      await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    } catch (saveError) {
      toast(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function createAdmin() {
    if (!newPhone.trim()) {
      toast("شماره موبایل مدیر جدید را وارد کنید.");
      return;
    }
    setCreating(true);
    try {
      const created = await api<AdminUser>("/admin/users", {
        method: "POST",
        body: JSON.stringify({ phone: newPhone.trim(), full_name: newName.trim() || null }),
      });
      await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setCreateOpen(false);
      setNewPhone("");
      setNewName("");
      setEditing(created);
      setRole("admin");
      setSelected([]);
      toast("مدیر ساخته شد؛ دسترسی ماژول‌ها را انتخاب کنید.");
    } catch (createError) {
      toast(errorMessage(createError));
    } finally {
      setCreating(false);
    }
  }

  const userColumns: DataColumn<AdminUser>[] = [
    {
      key: "user",
      header: "کاربر",
      cell: (user) => (
        <div>
          <p className="font-bold text-slate-900">
            {user.full_name || "بدون نام"}
            {user.id === me?.id && (
              <span className="mr-2 text-[11px] font-normal text-brand-600">(شما)</span>
            )}
          </p>
          <p className="mt-0.5 text-xs text-slate-500" dir="ltr">
            {formatPhone(user.phone)}
          </p>
        </div>
      ),
    },
    {
      key: "role",
      header: "نقش",
      cell: (user) => <RoleBadge role={user.role} label={ROLE_LABELS[user.role]} />,
    },
    {
      key: "permissions",
      header: "دسترسی‌ها",
      cell: (user) => (
        <Badge tone={user.role === "admin" ? "amber" : "slate"}>
          {user.role === "admin"
            ? `${user.permissions.length} دسترسی`
            : user.role === "superadmin"
              ? "دسترسی کامل"
              : "بدون دسترسی مدیریتی"}
        </Badge>
      ),
    },
    {
      key: "created",
      header: "عضویت",
      cell: (user) => (
        <span className="text-xs text-slate-500">
          {user.created_at ? formatJalali(user.created_at) : "—"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-left",
      cell: (user) => (
        <Button size="sm" variant="outline" onClick={() => openEditor(user)}>
          ویرایش
        </Button>
      ),
    },
  ];

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">کاربران</h1>
          <p className="mt-1 text-xs text-slate-500">
            نقش و دسترسی‌های هر کاربر را مدیریت کنید. هر تغییر در گزارش رویدادها ثبت می‌شود.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            مدیر جدید
          </Button>
          <Button size="sm" variant="outline" onClick={reload} disabled={loading}>
            به‌روزرسانی
          </Button>
        </div>
      </header>

      <DataTable
        columns={userColumns}
        rows={filteredUsers}
        rowKey={(user) => user.id}
        loading={loading}
        error={error}
        empty="کاربری با این نقش پیدا نشد."
        minWidthClassName="min-w-[820px]"
        toolbar={
          <div className="flex items-center gap-2">
            <label htmlFor="role-filter" className="text-xs text-slate-500">
              فیلتر نقش
            </label>
            <select
              id="role-filter"
              value={roleFilter}
              onChange={(event) => setRoleFilter(event.target.value as "all" | Role)}
              className="h-10 w-64 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="all">همه نقش‌ها</option>
              <option value="customer">مشتری</option>
              <option value="owner">کسب‌وکار</option>
              <option value="admin">مدیر</option>
            </select>
          </div>
        }
      />

      <BottomSheet
        open={editing !== null}
        title={editing ? `ویرایش ${editing.full_name || formatPhone(editing.phone)}` : "ویرایش کاربر"}
        onClose={() => setEditing(null)}
        className="mx-auto w-full max-w-3xl"
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

      <BottomSheet
        open={createOpen}
        title="ساخت مدیر جدید"
        onClose={() => setCreateOpen(false)}
        className="mx-auto w-full max-w-3xl"
      >
        <div className="space-y-4">
          <div>
            <label htmlFor="new-admin-phone" className="mb-2 block text-sm font-medium text-slate-700">
              شماره موبایل
            </label>
            <Input
              id="new-admin-phone"
              dir="ltr"
              inputMode="tel"
              className="text-left"
              placeholder="0912 345 6789"
              value={newPhone}
              onChange={(event) => setNewPhone(event.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label htmlFor="new-admin-name" className="mb-2 block text-sm font-medium text-slate-700">
              نام نمایشی (اختیاری)
            </label>
            <Input
              id="new-admin-name"
              placeholder="مدیر محتوا"
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
            />
          </div>
          <p className="rounded-xl bg-slate-50 px-4 py-3 text-xs leading-6 text-slate-500">
            مدیر با نقش «مدیر» ساخته می‌شود. در مرحله بعد دسترسی هر ماژول را انتخاب می‌کنید.
            ورود با همان کد یکبارمصرف پیامکی انجام می‌شود.
          </p>
          <Button className="w-full" loading={creating} onClick={() => void createAdmin()}>
            ساخت مدیر
          </Button>
        </div>
      </BottomSheet>
    </section>
  );
}
