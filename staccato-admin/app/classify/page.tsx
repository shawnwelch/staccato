import ClassifyForm from "@/components/ClassifyForm";

export const dynamic = "force-dynamic";

export default function ClassifyPage() {
  return (
    <>
      <h1>Channel classification</h1>
      <p className="page-desc">
        Kick off pacing classification for an entire channel. The backend
        resolves the channel, picks its most recent N videos, and fans out one
        analyze job per video on the <code>batch</code> queue — so a 20-video
        run enqueues 20 analyze jobs plus the coordinator job returned below.
        Scores land in the normal pipeline as each job completes.
      </p>
      <ClassifyForm />
    </>
  );
}
