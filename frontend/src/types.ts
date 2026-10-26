export type Role = "customer" | "owner" | "admin" | "superadmin";

export interface User {
  id: string;
  phone: string;
  national_id?: string | null;
  full_name?: string | null;
  role: Role;
  permissions: string[];
  is_phone_verified: boolean;
  is_national_id_verified: boolean;
  last_login_at?: string | null;
  created_at?: string | null;
}

export interface PermissionItem {
  code: string;
  label: string;
  group: string;
}

export interface DevOtp {
  phone: string;
  otp: string;
  ttl_seconds: number;
  expires_at?: string | null;
}

export interface LoginResult {
  access: string;
  refresh: string;
  user: User;
}
