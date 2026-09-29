import EmailVerifyClient from "./EmailVerifyClient";

type EmailVerifyPageProps = {
  searchParams: Promise<{
    token?: string | string[];
    email?: string | string[];
  }>;
};

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export default async function EmailVerifyPage({
  searchParams,
}: EmailVerifyPageProps) {
  const params = await searchParams;

  return (
    <EmailVerifyClient
      token={firstParam(params.token)}
      initialEmail={firstParam(params.email)}
    />
  );
}
