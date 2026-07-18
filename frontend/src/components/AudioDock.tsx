import { Pause, Play, RotateCcw, RotateCw } from "lucide-react";
import { AudioPlayer } from "../hooks/useAudioPlayer";
import { formatTime } from "../utils/format";

type Props = {
  src: string;
  player: AudioPlayer;
};

export function AudioDock({ src, player }: Props) {
  const {
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
  } = player;

  return (
    <>
      <audio src={src} preload="metadata" {...audioProps} />
      <div className="audio-dock">
        <div className="audio-controls">
          <button type="button" className="skip-button" onClick={() => skip(-10)} aria-label="10초 뒤로"><RotateCcw size={18} /><span>10</span></button>
          <button type="button" className="play-button" onClick={togglePlay} disabled={!audioAvailable} aria-label={isPlaying ? "일시정지" : "재생"}>{isPlaying ? <Pause size={21} fill="currentColor" /> : <Play size={21} fill="currentColor" />}</button>
          <button type="button" className="skip-button" onClick={() => skip(10)} aria-label="10초 앞으로"><RotateCw size={18} /><span>10</span></button>
        </div>
        <span className="player-time">{formatTime(currentTime)}</span>
        <input
          className="player-range"
          type="range"
          min="0"
          max={Math.max(1, visibleDuration)}
          step="0.1"
          value={Math.min(currentTime, Math.max(1, visibleDuration))}
          onChange={(event) => seekTo(Number(event.target.value), false)}
          aria-label="재생 위치"
        />
        <span className="player-time">{formatTime(visibleDuration)}</span>
        <button className="rate-button" type="button" onClick={cyclePlaybackRate}>{playbackRate}x</button>
        {!audioAvailable ? <span className="audio-unavailable">오디오 만료</span> : null}
      </div>
    </>
  );
}
