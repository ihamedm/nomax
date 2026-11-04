import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

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

type VerifiedFilter = "all" | "verified" | "unverified";

interface UserFormState {
  full_name: string;
  national_id: string;
  role: Role;
  permissions: string[];
  is_verified: boolean;
  is_phone_verified: boolean;
}

function emptyForm(): UserFormState {
  return {
    full_name: "",
    national_id: "",
    role: "customer",
    permissions: [],
    is_verified: false,
    is_phone_verified: false,
  };
}

function PermissionPicker({
  groups,
  selected,
  onToggle,
  onClear,
}: {
  groups: [string, PermissionItem[]][];
  selected: string[];
  onToggle: (code: string) => void;
  onClear: () => void;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">دسترسی‌ها</p>
        <button type="button" className="text-xs text-brand-600" onClick={onClear}>
          پاک کردن همه
        </button>
      </div>
      <div className="max-h-[38dvh] space-y-4 overflow-y-auto rounded-2xl border border-slate-200 bg-slate-50/60 p-3">
        {groups.map(([group, items]) => (
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
                      onChange={() => onToggle(item.code)}
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
  );
}

function VerificationFields({
  form,
  disabled,
  onChange,
}: {
  form: UserFormState;
  disabled?: boolean;
  onChange: (patch: Partial<UserFormState>) => void;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3">
        <input
          type="checkbox"
          checked={form.is_verified}
          disabled={disabled}
          onChange={(event) => onChange({ is_verified: event.target.checked })}
          className="mt-0.5 h-4 w-4 accent-brand-600"
        />
        <span>
          <span className="block text-sm font-medium text-slate-800">حساب تأییدشده</span>
          <span className="mt-0.5 block text-[11px] leading-5 text-slate-500">
            کاربران ثبت‌نام‌شده با کد یکبارمصرف خودکار تأیید می‌شوند. کاربران ساخته‌شده
            از داشبورد یا ایمپورت‌ها به‌طور پیش‌فرض تأییدنشده‌اند.
          </span>
        </span>
      </label>
      <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3">
        <input
          type="checkbox"
          checked={form.is_phone_verified}
          disabled={disabled}
          onChange={(event) => onChange({ is_phone_verified: event.target.checked })}
          className="mt-0.5 h-4 w-4 accent-brand-600"
        />
        <span>
          <span className="block text-sm font-medium text-slate-800">شماره تأییدشده</span>
          <span className="mt-0.5 block text-[11px] leading-5 text-slate-500">
            تأیید مالکیت شماره موبایل؛ این وضعیت معمولاً پس از ورود با کد یکبارمصرف
            فعال می‌شود.
          </span>
        </span>
      </label>
    </div>
  );
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
  const [form, setForm] = useState<UserFormState>(emptyForm);
  const [saving, setSaving] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [newPhone, setNewPhone] = useState("");
  const [newForm, setNewForm] = useState<UserFormState>(emptyForm);
  const [creating, setCreating] = useState(false);

  const [roleFilter, setRoleFilter] = useState<"all" | Role>("all");
  const [verifiedFilter, setVerifiedFilter] = useState<VerifiedFilter>("all");

  const filteredUsers = users.filter((user) => {
    if (roleFilter !== "all" && user.role !== roleFilter) return false;
    if (verifiedFilter === "verified" && !user.is_verified) return false;
    if (verifiedFilter === "unverified" && user.is_verified) return false;
    return true;
  });

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
    setForm({
      full_name: user.full_name ?? "",
      national_id: user.national_id ?? "",
      role: user.role,
      permissions: user.permissions,
      is_verified: user.is_verified,
      is_phone_verified: user.is_phone_verified,
    });
  }

  function openCreate() {
    setNewPhone("");
    setNewForm(emptyForm());
    setCreateOpen(true);
  }

  function togglePermission(
    code: string,
    target: "edit" | "create",
  ) {
    const update = (current: UserFormState): UserFormState => ({
      ...current,
      permissions: current.permissions.includes(code)
        ? current.permissions.filter((item) => item !== code)
        : [...current.permissions, code],
    });
    if (target === "edit") setForm(update);
    else setNewForm(update);
  }

  function buildPayload(state: UserFormState) {
    return {
      full_name: state.full_name.trim() || null,
      national_id: state.national_id.trim() || null,
      role: state.role,
      permissions: state.role === "admin" ? state.permissions : [],
      is_verified: state.is_verified,
      is_phone_verified: state.is_phone_verified,
    };
  }

  async function save() {
    if (!editing) return;
    setSaving(true);
    try {
      await api(`/admin/users/${editing.id}`, {
        method: "PATCH",
        body: JSON.stringify(buildPayload(form)),
      });
      toast("تغییرات کاربر ذخیره شد.");
      setEditing(null);
      await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    } catch (saveError) {
      toast(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function createUser() {
    if (!newPhone.trim()) {
      toast("شماره موبایل کاربر جدید را وارد کنید.");
      return;
    }
    setCreating(true);
    try {
      await api<AdminUser>("/admin/users", {
        method: "POST",
        body: JSON.stringify({ phone: newPhone.trim(), ...buildPayload(newForm) }),
      });
      await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      setCreateOpen(false);
      toast("کاربر ساخته شد.");
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
          {user.national_id && (
            <p className="mt-0.5 text-[10px] text-slate-400" dir="ltr">
              {user.national_id}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "role",
      header: "نقش",
      cell: (user) => <RoleBadge role={user.role} label={ROLE_LABELS[user.role]} />,
    },
    {
      key: "verified",
      header: "وضعیت تأیید",
      cell: (user) => (
        <Badge tone={user.is_verified ? "brand" : "slate"}>
          {user.is_verified ? "تأییدشده" : "تأییدنشده"}
        </Badge>
      ),
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
        <div className="flex flex-wrap items-center justify-end gap-3">
          <div className="flex items-center gap-3 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100">
            <button
              type="button"
              onClick={() => openEditor(user)}
              className="text-xs font-medium text-brand-600 hover:text-brand-700 hover:underline"
            >
              ویرایش
            </button>
          </div>
          <Link
            to={`/admin/businesses?owner_id=${user.id}&owner_name=${encodeURIComponent(
              user.full_name || user.phone,
            )}`}
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-brand-300 hover:text-brand-700"
          >
            نمایش کسب‌وکارها
          </Link>
        </div>
      ),
    },
  ];

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">کاربران</h1>
          <p className="mt-1 text-xs text-slate-500">
            کاربران همه نقش‌ها را بسازید و نام نمایشی، اطلاعات هویتی، نقش، دسترسی و
            وضعیت تأیید را مدیریت کنید. هر تغییر در گزارش رویدادها ثبت می‌شود.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={openCreate}>
            کاربر جدید
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
        empty="کاربری با این فیلترها پیدا نشد."
        minWidthClassName="min-w-[960px]"
        toolbar={
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <label htmlFor="role-filter" className="text-xs text-slate-500">
                فیلتر نقش
              </label>
              <select
                id="role-filter"
                value={roleFilter}
                onChange={(event) => setRoleFilter(event.target.value as "all" | Role)}
                className="h-10 w-56 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              >
                <option value="all">همه نقش‌ها</option>
                <option value="customer">مشتری</option>
                <option value="owner">کسب‌وکار</option>
                <option value="admin">مدیر</option>
                <option value="superadmin">مدیر کل</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="verified-filter" className="text-xs text-slate-500">
                وضعیت تأیید
              </label>
              <select
                id="verified-filter"
                value={verifiedFilter}
                onChange={(event) => setVerifiedFilter(event.target.value as VerifiedFilter)}
                className="h-10 w-48 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              >
                <option value="all">همه کاربران</option>
                <option value="verified">تأییدشده</option>
                <option value="unverified">تأییدنشده</option>
              </select>
            </div>
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
            <div className="rounded-xl bg-slate-50 px-4 py-3">
              <p className="text-[11px] text-slate-500">شماره موبایل (شناسه ورود)</p>
              <p className="mt-1 text-sm font-bold text-slate-800" dir="ltr">
                {formatPhone(editing.phone)}
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="admin-full-name"
                  className="mb-2 block text-sm font-medium text-slate-700"
                >
                  نام نمایشی
                </label>
                <Input
                  id="admin-full-name"
                  placeholder="مثلاً علی رضایی"
                  value={form.full_name}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, full_name: event.target.value }))
                  }
                />
              </div>
              <div>
                <label
                  htmlFor="admin-national-id"
                  className="mb-2 block text-sm font-medium text-slate-700"
                >
                  کد ملی (اختیاری)
                </label>
                <Input
                  id="admin-national-id"
                  dir="ltr"
                  inputMode="numeric"
                  maxLength={10}
                  className="text-left"
                  placeholder="۱۰ رقم"
                  value={form.national_id}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, national_id: event.target.value }))
                  }
                />
              </div>
            </div>

            <div>
              <label htmlFor="admin-role" className="mb-2 block text-sm font-medium text-slate-700">
                نقش
              </label>
              <select
                id="admin-role"
                value={form.role}
                disabled={editing.id === me?.id || saving}
                onChange={(event) =>
                  setForm((current) => ({ ...current, role: event.target.value as Role }))
                }
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

            {form.role === "admin" ? (
              <PermissionPicker
                groups={groupedPermissions}
                selected={form.permissions}
                onToggle={(code) => togglePermission(code, "edit")}
                onClear={() => setForm((current) => ({ ...current, permissions: [] }))}
              />
            ) : (
              <p className="rounded-xl bg-slate-50 px-4 py-3 text-xs leading-6 text-slate-500">
                دسترسی‌های دقیق فقط برای نقش «مدیر» معنا دارد. نقش‌های مشتری، کسب‌وکار و
                مدیر کل از قواعد ثابت خودشان پیروی می‌کنند.
              </p>
            )}

            <VerificationFields
              form={form}
              disabled={saving}
              onChange={(patch) => setForm((current) => ({ ...current, ...patch }))}
            />

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
        title="ساخت کاربر جدید"
        onClose={() => setCreateOpen(false)}
        className="mx-auto w-full max-w-3xl"
      >
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="new-user-phone"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                شماره موبایل
              </label>
              <Input
                id="new-user-phone"
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
              <label
                htmlFor="new-user-name"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                نام نمایشی (اختیاری)
              </label>
              <Input
                id="new-user-name"
                placeholder="مثلاً علی رضایی"
                value={newForm.full_name}
                onChange={(event) =>
                  setNewForm((current) => ({ ...current, full_name: event.target.value }))
                }
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="new-user-national-id"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                کد ملی (اختیاری)
              </label>
              <Input
                id="new-user-national-id"
                dir="ltr"
                inputMode="numeric"
                maxLength={10}
                className="text-left"
                placeholder="۱۰ رقم"
                value={newForm.national_id}
                onChange={(event) =>
                  setNewForm((current) => ({ ...current, national_id: event.target.value }))
                }
              />
            </div>
            <div>
              <label
                htmlFor="new-user-role"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                نقش
              </label>
              <select
                id="new-user-role"
                value={newForm.role}
                onChange={(event) =>
                  setNewForm((current) => ({ ...current, role: event.target.value as Role }))
                }
                className="h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              >
                {ROLES.map((item) => (
                  <option key={item} value={item}>
                    {ROLE_LABELS[item]}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {newForm.role === "admin" ? (
            <PermissionPicker
              groups={groupedPermissions}
              selected={newForm.permissions}
              onToggle={(code) => togglePermission(code, "create")}
              onClear={() => setNewForm((current) => ({ ...current, permissions: [] }))}
            />
          ) : (
            <p className="rounded-xl bg-slate-50 px-4 py-3 text-xs leading-6 text-slate-500">
              دسترسی‌های دقیق فقط برای نقش «مدیر» انتخاب می‌شوند. برای مدیر کل دسترسی
              کامل و برای مشتری و کسب‌وکار قواعد ثابت اعمال می‌شود.
            </p>
          )}

          <VerificationFields
            form={newForm}
            disabled={creating}
            onChange={(patch) => setNewForm((current) => ({ ...current, ...patch }))}
          />

          <p className="rounded-xl bg-slate-50 px-4 py-3 text-xs leading-6 text-slate-500">
            ورود کاربر با همان کد یکبارمصرف پیامکی انجام می‌شود. اگر «حساب تأییدشده» را
            فعال نکنید، کاربر تا بررسی و تأیید شما تأییدنشده می‌ماند.
          </p>
          <Button className="w-full" loading={creating} onClick={() => void createUser()}>
            ساخت کاربر
          </Button>
        </div>
      </BottomSheet>
    </section>
  );
}
