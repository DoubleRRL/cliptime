import { redirect } from "next/navigation";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function TaskEditPage({ params }: PageProps) {
  await params;
  redirect("/");
}
