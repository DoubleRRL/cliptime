import { redirect } from "next/navigation";
import { SignUp } from "@/components/auth/sign-up";
import Link from "next/link";

function isLocalSingleUserModeEnabled(): boolean {
  const value = process.env.LOCAL_SINGLE_USER;
  if (value === undefined || value === "") return true;
  const normalized = value.trim().toLowerCase();
  return !["0", "false", "no", "off"].includes(normalized);
}

export default function SignUpPage() {
  if (isLocalSingleUserModeEnabled()) {
    redirect("/");
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <SignUp />
        <div className="text-center">
          <p className="text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/sign-in" className="font-medium text-foreground hover:text-muted-foreground">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
