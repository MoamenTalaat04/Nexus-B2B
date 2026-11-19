import { Logo } from "@/components/shared/logo";
import { LoginForm } from "@/features/auth/components/login-form";

export default function LoginPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-center md:hidden">
        <Logo />
      </div>
      <LoginForm />
    </div>
  );
}
