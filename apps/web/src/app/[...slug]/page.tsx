import { ProductPage } from "@/components/product-page";

export default async function ProductRoute({
  params,
}: {
  params: Promise<{ slug?: string[] }>;
}) {
  const resolved = await params;
  const slug = resolved.slug?.join("/") ?? "dashboard";
  return <ProductPage slug={slug} />;
}
