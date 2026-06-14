import { getOrCreateLocalUser } from "@/server/local-user";

export type EffectiveSession = {
  user: {
    id: string;
    name: string;
    email: string;
    is_admin?: boolean;
  };
};

export async function getEffectiveSession(): Promise<EffectiveSession | null> {
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

/** @deprecated Use getEffectiveSession */
export async function getServerSession() {
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
