import { SyntheticEvent, useRef, useState } from "react";

export function useAudioPlayer(fallbackDuration: number) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [audioAvailable, setAudioAvailable] = useState(true);

  const visibleDuration = duration || fallbackDuration;

  const seekTo = (seconds: number, autoplay = true) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, seconds);
    setCurrentTime(audio.currentTime);
    if (autoplay) void audio.play().catch(() => setIsPlaying(false));
  };

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) void audio.play().catch(() => setIsPlaying(false));
    else audio.pause();
  };

  const skip = (seconds: number) => seekTo(Math.min(visibleDuration, Math.max(0, currentTime + seconds)), false);

  const cyclePlaybackRate = () => {
    const rates = [1, 1.25, 1.5, 2];
    const next = rates[(rates.indexOf(playbackRate) + 1) % rates.length];
    setPlaybackRate(next);
    if (audioRef.current) audioRef.current.playbackRate = next;
  };

  const audioProps = {
    ref: audioRef,
    onLoadedMetadata: (event: SyntheticEvent<HTMLAudioElement>) => setDuration(event.currentTarget.duration),
    onTimeUpdate: (event: SyntheticEvent<HTMLAudioElement>) => setCurrentTime(event.currentTarget.currentTime),
    onPlay: () => setIsPlaying(true),
    onPause: () => setIsPlaying(false),
    onEnded: () => setIsPlaying(false),
    onError: () => setAudioAvailable(false),
  };

  return {
    isPlaying,
    currentTime,
    visibleDuration,
    playbackRate,
    audioAvailable,
    seekTo,
    togglePlay,
    skip,
    cyclePlaybackRate,
    audioProps,
  };
}

export type AudioPlayer = ReturnType<typeof useAudioPlayer>;
