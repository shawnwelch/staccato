export default function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="notice error">
      <strong>Backend error.</strong> {message}
      <div style={{ marginTop: 4, fontSize: 12 }}>
        Check that BACKEND_URL is reachable and ADMIN_API_TOKEN is valid, then
        reload.
      </div>
    </div>
  );
}
