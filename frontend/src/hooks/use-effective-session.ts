"use client";

import { useEffect, useState } from "react";

import { useSession } from "@/lib/auth-client";
import { isLocalSingleUserMode } from "@/lib/app-flags";

export type EffectiveUser = {
  id: string;
  name: string;
  email: string;
  is_admin?: boolean;
};

type EffectiveSessionState = {
  user: EffectiveUser | null;
  isPending: boolean;
};

let cachedLocalUser: EffectiveUser | null = null;
let localUserPromise: Promise<EffectiveUser | null> | null = null;

async function fetchLocalUser(): Promise<EffectiveUser | null> {
  if (cachedLocalUser) {
    return cachedLocalUser;
  }

  if (!localUserPromise) {
    localUserPromise = fetch("/api/me", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return null;
        const data = await response.json();
        const user = data.user as EffectiveUser | undefined;
        if (user?.id) {
          cachedLocalUser = user;
          return user;
        }
        return null;
      })
      .catch(() => null)
      .finally(() => {
        localUserPromise = null;
      });
  }

  return localUserPromise;
}

export function useEffectiveSession(): EffectiveSessionState {
  const authSession = useSession();
  const [localUser, setLocalUser] = useState<EffectiveUser | null>(
    isLocalSingleUserMode ? cachedLocalUser : null,
  );
  const [localPending, setLocalPending] = useState(isLocalSingleUserMode);

  useEffect(() => {
    if (!isLocalSingleUserMode) return;

    let cancelled = false;
    void fetchLocalUser().then((user) => {
      if (cancelled) return;
      setLocalUser(user);
      setLocalPending(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  if (isLocalSingleUserMode) {
    return {
      user: localUser,
      isPending: localPending,
    };
  }

  const user = authSession.data?.user;
  return {
    user: user
      ? {
          id: user.id,
          name: user.name,
          email: user.email,
          is_admin: Boolean((user as { is_admin?: boolean }).is_admin),
        }
      : null,
    isPending: authSession.isPending,
  };
}
