import PasswordResetConfirmClient from "./PasswordResetConfirmClient";

type PasswordResetConfirmPageProps = {
  searchParams: Promise<{
    token?: string | string[];
  }>;
};

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export default async function PasswordResetConfirmPage({
  searchParams,
}: PasswordResetConfirmPageProps) {
  const params = await searchParams;

  return (
    <PasswordResetConfirmClient
      token={firstParam(params.token)}
    />
  );
}
