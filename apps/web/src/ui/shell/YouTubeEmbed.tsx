import { youtubeEmbedUrl } from '@/lib/youtube';
import { cn } from '@/lib/cn';

type YouTubeEmbedSize = 'sm' | 'md' | 'lg';

export function YouTubeEmbed({
  videoId,
  title,
  size = 'sm',
  className,
}: {
  videoId: string;
  title?: string;
  size?: YouTubeEmbedSize;
  className?: string;
}) {
  const sizeClass =
    size === 'lg'
      ? 'w-full'
      : size === 'md'
        ? 'max-w-[360px]'
        : 'max-w-[240px]';

  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl border border-[color:var(--border)] bg-[var(--surface-muted)]',
        sizeClass,
        className
      )}
    >
      <div className="aspect-video">
        <iframe
          title={title ?? 'YouTube video preview'}
          src={youtubeEmbedUrl(videoId)}
          className="h-full w-full"
          loading="lazy"
          referrerPolicy="strict-origin-when-cross-origin"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
        />
      </div>
    </div>
  );
}
