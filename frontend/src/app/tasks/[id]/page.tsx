import { redirect } from "next/navigation";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function TaskDetailPage({ params }: PageProps) {
  await params;
  redirect("/");
}
