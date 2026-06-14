"use client";

import { useEffect, useState } from "react";

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
  const [localUser, setLocalUser] = useState<EffectiveUser | null>(cachedLocalUser);
  const [localPending, setLocalPending] = useState(!cachedLocalUser);

  useEffect(() => {
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

  return {
    user: localUser,
    isPending: localPending,
  };
}
