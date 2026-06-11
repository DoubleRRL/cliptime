import { headers } from "next/headers";

import { auth } from "@/lib/auth";
import { getOrCreateLocalUser } from "@/server/local-user";

function isLocalSingleUserModeEnabled(): boolean {
  const value = process.env.LOCAL_SINGLE_USER;
  if (value === undefined || value === "") return true;
  const normalized = value.trim().toLowerCase();
  return !["0", "false", "no", "off"].includes(normalized);
}

export type EffectiveSession = {
  user: {
    id: string;
    name: string;
    email: string;
    is_admin?: boolean;
  };
};

export async function getEffectiveSession(): Promise<EffectiveSession | null> {
  if (isLocalSingleUserModeEnabled()) {
    const user = await getOrCreateLocalUser();
    return {
      user: {
        id: user.id,
        name: user.name,
        email: user.email,
        is_admin: user.is_admin,
      },
    };
  }

  const session = await auth.api.getSession({ headers: await headers() });
  if (!session?.user?.id) {
    return null;
  }

  return {
    user: {
      id: session.user.id,
      name: session.user.name,
      email: session.user.email,
      is_admin: Boolean((session.user as { is_admin?: boolean }).is_admin),
    },
  };
}

/** @deprecated Use getEffectiveSession */
export async function getServerSession() {
  if (isLocalSingleUserModeEnabled()) {
    const user = await getOrCreateLocalUser();
    return {
      user: {
        id: user.id,
        name: user.name,
        email: user.email,
        is_admin: user.is_admin,
      },
    };
  }
  return auth.api.getSession({ headers: await headers() });
}
