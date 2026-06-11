import { randomUUID } from "crypto";

import { hashPassword } from "better-auth/crypto";

import prisma from "@/lib/prisma";

const LOCAL_EMAIL = "local@supoclip.local";

export type LocalUserRecord = {
  id: string;
  name: string;
  email: string;
  is_admin: boolean;
};

let cachedUser: LocalUserRecord | null = null;

export async function getOrCreateLocalUser(): Promise<LocalUserRecord> {
  if (cachedUser) {
    return cachedUser;
  }

  const existing = await prisma.user.findUnique({
    where: { email: LOCAL_EMAIL },
    select: { id: true, name: true, email: true, is_admin: true },
  });

  if (existing) {
    cachedUser = existing;
    return existing;
  }

  const now = new Date();
  const user = await prisma.user.create({
    data: {
      email: LOCAL_EMAIL,
      name: "Local",
      is_admin: true,
    },
    select: { id: true, name: true, email: true, is_admin: true },
  });

  const passwordHash = await hashPassword(randomUUID());
  await prisma.account.create({
    data: {
      id: randomUUID(),
      accountId: user.id,
      providerId: "credential",
      userId: user.id,
      password: passwordHash,
      createdAt: now,
      updatedAt: now,
    },
  });

  cachedUser = user;
  return user;
}
