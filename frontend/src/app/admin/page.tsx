import Link from "next/link";
import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import prisma from "@/lib/prisma";
import { AdminUserToggle } from "@/components/admin/admin-user-toggle";
import { Badge } from "@/components/ui/badge";

const ACTIVE_TASK_STATUSES = ["queued", "processing", "pending"];

function statusBadgeClass(status: string) {
  if (status === "completed") return "border border-green-500/20 bg-green-500/15 text-green-400";
  if (status === "processing" || status === "queued" || status === "pending") return "border border-blue-500/20 bg-blue-500/15 text-blue-400";
  if (status === "error" || status === "failed") return "border border-red-500/20 bg-red-500/15 text-red-400";
  if (status === "cancelled") return "border border-border bg-muted/50 text-muted-foreground";
  return "border border-border bg-muted/50 text-muted-foreground";
}

export default async function AdminPage({
  searchParams,
}: {
  searchParams: Promise<{ user?: string }>;
}) {
  const session = await auth.api.getSession({ headers: await headers() });

  if (!session?.user) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16">
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="mt-3 text-sm text-muted-foreground">You need to sign in to view this page.</p>
        <Link href="/sign-in" className="mt-6 inline-block text-sm font-medium text-foreground underline">
          Go to sign in
        </Link>
      </main>
    );
  }

  const isAdmin = Boolean((session.user as { is_admin?: boolean }).is_admin);

  if (!isAdmin) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16">
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="mt-3 text-sm text-muted-foreground">You are signed in, but your account is not an admin.</p>
      </main>
    );
  }

  const { user: selectedUserId } = await searchParams;

  const [
    totalUsers,
    adminUsers,
    totalTasks,
    completedTasks,
    activeTasks,
    recentUsers,
    processingNow,
    recentGenerations,
    tasksByUser,
    selectedUser,
    selectedUserTasks,
  ] = await Promise.all([
    prisma.user.count(),
    prisma.user.count({ where: { is_admin: true } }),
    prisma.task.count(),
    prisma.task.count({ where: { status: "completed" } }),
    prisma.task.count({ where: { status: { in: ACTIVE_TASK_STATUSES } } }),
    prisma.user.findMany({
      orderBy: { createdAt: "desc" },
      take: 30,
      select: {
        id: true,
        email: true,
        name: true,
        is_admin: true,
        plan: true,
        createdAt: true,
      },
    }),
    prisma.task.findMany({
      where: { status: { in: ACTIVE_TASK_STATUSES } },
      orderBy: { updated_at: "desc" },
      take: 25,
      select: {
        id: true,
        status: true,
        created_at: true,
        updated_at: true,
        user: {
          select: {
            id: true,
            email: true,
          },
        },
        source: {
          select: {
            title: true,
          },
        },
      },
    }),
    prisma.task.findMany({
      orderBy: { created_at: "desc" },
      take: 40,
      select: {
        id: true,
        status: true,
        created_at: true,
        generated_clips_ids: true,
        user: {
          select: {
            id: true,
            email: true,
          },
        },
        source: {
          select: {
            title: true,
            type: true,
          },
        },
      },
    }),
    prisma.task.groupBy({
      by: ["user_id"],
      _count: {
        _all: true,
      },
    }),
    selectedUserId
      ? prisma.user.findUnique({
          where: { id: selectedUserId },
          select: {
            id: true,
            email: true,
            name: true,
            is_admin: true,
          },
        })
      : Promise.resolve(null),
    selectedUserId
      ? prisma.task.findMany({
          where: { user_id: selectedUserId },
          orderBy: { created_at: "desc" },
          take: 40,
          select: {
            id: true,
            status: true,
            created_at: true,
            generated_clips_ids: true,
            source: {
              select: {
                title: true,
                type: true,
              },
            },
          },
        })
      : Promise.resolve([]),
  ]);

  const generationCountByUser = new Map(tasksByUser.map((item) => [item.user_id, item._count._all]));

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Admin Dashboard</h1>
          <p className="mt-2 text-sm text-muted-foreground">Manage users and monitor overall platform activity.</p>
        </div>
        <Link href="/" className="text-sm font-medium text-foreground underline">
          Back to app
        </Link>
      </div>

      <section className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Total users</p>
          <p className="mt-2 text-2xl font-semibold text-foreground">{totalUsers}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Admins</p>
          <p className="mt-2 text-2xl font-semibold text-foreground">{adminUsers}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Total tasks</p>
          <p className="mt-2 text-2xl font-semibold text-foreground">{totalTasks}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Completed tasks</p>
          <p className="mt-2 text-2xl font-semibold text-foreground">{completedTasks}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 sm:col-span-2 lg:col-span-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Currently processing</p>
          <p className="mt-2 text-2xl font-semibold text-foreground">{activeTasks}</p>
        </div>
      </section>

      <section className="mt-8 rounded-lg border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-lg font-medium">Currently Processing Tasks</h2>
          <p className="text-sm text-muted-foreground">Live queue across all users.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-muted/40">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Task</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">User</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-card">
              {processingNow.length === 0 ? (
                <tr>
                  <td className="px-4 py-4 text-sm text-muted-foreground" colSpan={4}>No tasks are currently processing.</td>
                </tr>
              ) : (
                processingNow.map((task) => (
                  <tr key={task.id}>
                    <td className="px-4 py-3">
                      <Link href={`/tasks/${task.id}`} className="text-sm font-medium text-foreground underline">
                        {task.id}
                      </Link>
                      <p className="text-xs text-muted-foreground truncate max-w-[420px]">{task.source?.title || "Untitled source"}</p>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">{task.user.email}</td>
                    <td className="px-4 py-3">
                      <Badge className={statusBadgeClass(task.status)}>{task.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">{task.updated_at.toLocaleString()}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
      <section className="mt-8 rounded-lg border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-lg font-medium">Recent Generations</h2>
          <p className="text-sm text-muted-foreground">Latest task activity across the platform.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-muted/40">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Task</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">User</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Clips</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-card">
              {recentGenerations.map((task) => (
                <tr key={task.id}>
                  <td className="px-4 py-3">
                    <Link href={`/tasks/${task.id}`} className="text-sm font-medium text-foreground underline">
                      {task.id}
                    </Link>
                    <p className="text-xs text-muted-foreground truncate max-w-[420px]">{task.source?.title || "Untitled source"}</p>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">{task.user.email}</td>
                  <td className="px-4 py-3">
                    <Badge className={statusBadgeClass(task.status)}>{task.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">{task.generated_clips_ids.length}</td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">{task.created_at.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-8 rounded-lg border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-lg font-medium">Users</h2>
          <p className="text-sm text-muted-foreground">Most recent users. Toggle admin access and inspect user tasks.</p>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-muted/40">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">User</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Plan</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Role</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Generations</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Created</th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wide text-muted-foreground">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-card">
              {recentUsers.map((user) => (
                <tr key={user.id}>
                  <td className="px-4 py-3">
                    <p className="text-sm font-medium text-foreground">{user.name || "Unnamed user"}</p>
                    <p className="text-xs text-muted-foreground">{user.email}</p>
                    <Link href={`/admin?user=${user.id}`} className="text-xs text-foreground underline">
                      View user tasks
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className="capitalize">
                      {user.plan}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    {user.is_admin ? (
                      <Badge className="bg-primary text-primary-foreground">Admin</Badge>
                    ) : (
                      <Badge variant="outline">User</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">{generationCountByUser.get(user.id) || 0}</td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">{user.createdAt.toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-right">
                    <AdminUserToggle
                      userId={user.id}
                      isAdmin={user.is_admin}
                      isCurrentUser={user.id === session.user.id}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-8 rounded-lg border border-border bg-card">
        <div className="border-b border-border px-4 py-3 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium">User Task Explorer</h2>
            <p className="text-sm text-muted-foreground">Inspect generations for a specific user.</p>
          </div>
          {selectedUserId && (
            <Link href="/admin" className="text-sm font-medium text-foreground underline">
              Clear filter
            </Link>
          )}
        </div>

        {!selectedUser ? (
          <div className="px-4 py-5 text-sm text-muted-foreground">Select a user from the table above to view their tasks.</div>
        ) : (
          <div className="overflow-x-auto">
            <div className="px-4 py-3 text-sm text-muted-foreground border-b border-border">
              Viewing: <span className="font-medium text-foreground">{selectedUser.name || selectedUser.email}</span> ({selectedUser.email})
            </div>
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted/40">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Task</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Source</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Clips</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-card">
                {selectedUserTasks.length === 0 ? (
                  <tr>
                    <td className="px-4 py-4 text-sm text-muted-foreground" colSpan={5}>No tasks found for this user.</td>
                  </tr>
                ) : (
                  selectedUserTasks.map((task) => (
                    <tr key={task.id}>
                      <td className="px-4 py-3">
                        <Link href={`/tasks/${task.id}`} className="text-sm font-medium text-foreground underline">
                          {task.id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">{task.source?.title || "Untitled source"}</td>
                      <td className="px-4 py-3">
                        <Badge className={statusBadgeClass(task.status)}>{task.status}</Badge>
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">{task.generated_clips_ids.length}</td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">{task.created_at.toLocaleString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
