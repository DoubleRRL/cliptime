import { redirect } from "next/navigation";
import { SignIn } from "@/components/auth/sign-in";
import Link from "next/link";

function isLocalSingleUserModeEnabled(): boolean {
  const value = process.env.LOCAL_SINGLE_USER;
  if (value === undefined || value === "") return true;
  const normalized = value.trim().toLowerCase();
  return !["0", "false", "no", "off"].includes(normalized);
}

export default function SignInPage() {
  if (isLocalSingleUserModeEnabled()) {
    redirect("/");
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <SignIn />
        <div className="text-center">
          <p className="text-sm text-muted-foreground">
            Don&apos;t have an account?{" "}
            <Link href="/sign-up" className="font-medium text-foreground hover:text-muted-foreground">
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
