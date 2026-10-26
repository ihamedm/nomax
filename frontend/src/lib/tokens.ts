const ACCESS_KEY = "nomax.access";
const REFRESH_KEY = "nomax.refresh";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Private mode / storage disabled: keep the session in memory only.
  }
}

let access = read(ACCESS_KEY);
let refresh = read(REFRESH_KEY);

export const tokens = {
  get access(): string | null {
    return access;
  },
  get refresh(): string | null {
    return refresh;
  },
  set(nextAccess: string, nextRefresh: string): void {
    access = nextAccess;
    refresh = nextRefresh;
    write(ACCESS_KEY, nextAccess);
    write(REFRESH_KEY, nextRefresh);
  },
  clear(): void {
    access = null;
    refresh = null;
    write(ACCESS_KEY, null);
    write(REFRESH_KEY, null);
  },
};
