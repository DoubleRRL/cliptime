"use client";

import { useEffect, useRef } from "react";

import { useEffectiveSession } from "@/hooks/use-effective-session";
import { identify } from "@/lib/datafast";

export function DataFastIdentity() {
  const { user } = useEffectiveSession();
  const lastPayloadRef = useRef<string | null>(null);

  useEffect(() => {
    if (!user?.id) {
      lastPayloadRef.current = null;
      return;
    }

    const payload = {
      user_id: user.id,
      ...(user.name ? { name: user.name } : {}),
      is_admin: String(Boolean(user.is_admin)),
    };
    const serializedPayload = JSON.stringify(payload);

    if (serializedPayload === lastPayloadRef.current) {
      return;
    }

    identify(payload);
    lastPayloadRef.current = serializedPayload;
  }, [user]);

  return null;
}
