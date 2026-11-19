import { Logo } from "@/components/shared/logo";
import { SignupForm } from "@/features/auth/components/signup-form";

export default function SignupPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-center md:hidden">
        <Logo />
      </div>
      <SignupForm />
    </div>
  );
}

