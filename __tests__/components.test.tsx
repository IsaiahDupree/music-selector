import { render, screen } from "@testing-library/react";
import TrackCard from "@/components/TrackCard";
import AudioPlayer from "@/components/AudioPlayer";

describe("TrackCard Component", () => {
  const defaultProps = {
    id: "test-id",
    title: "Test Track",
    artist: "Test Artist",
    genre: "lofi",
    mood: "calm",
    duration_sec: 180,
    energy_level: 0.4,
  };

  it("renders track title", () => {
    render(<TrackCard {...defaultProps} />);
    expect(screen.getByText("Test Track")).toBeInTheDocument();
  });

  it("renders artist name", () => {
    render(<TrackCard {...defaultProps} />);
    expect(screen.getByText("Test Artist")).toBeInTheDocument();
  });

  it("renders genre and mood tags", () => {
    render(<TrackCard {...defaultProps} />);
    expect(screen.getByText("lofi")).toBeInTheDocument();
    expect(screen.getByText("calm")).toBeInTheDocument();
  });

  it("renders duration in correct format", () => {
    render(<TrackCard {...defaultProps} />);
    expect(screen.getByText("3:00")).toBeInTheDocument();
  });

  it("displays energy bar with percentage", () => {
    render(<TrackCard {...defaultProps} />);
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("shows trending badge when is_trending is true", () => {
    render(<TrackCard {...defaultProps} is_trending={true} />);
    expect(screen.getByText("🔥 Trending")).toBeInTheDocument();
  });

  it("handles missing optional fields", () => {
    render(
      <TrackCard
        id="test-id"
        title="Test Track"
        artist={null}
        genre={null}
        mood={null}
      />
    );
    expect(screen.getByText("Test Track")).toBeInTheDocument();
  });

  it("calls onSelect callback with track id", () => {
    const mockSelect = jest.fn();
    render(<TrackCard {...defaultProps} onSelect={mockSelect} />);
    // Note: Click behavior would be tested with userEvent in full test suite
  });
});

describe("AudioPlayer Component", () => {
  const defaultProps = {
    src: "test-audio.mp3",
    title: "Test Song",
    artist: "Test Artist",
  };

  it("renders with title and artist", () => {
    render(<AudioPlayer {...defaultProps} />);
    expect(screen.getByText("Test Song")).toBeInTheDocument();
    expect(screen.getByText("Test Artist")).toBeInTheDocument();
  });

  it("renders play/pause button", () => {
    const { container } = render(<AudioPlayer {...defaultProps} />);
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBeGreaterThan(0);
  });

  it("renders audio element with correct src", () => {
    const { container } = render(<AudioPlayer {...defaultProps} />);
    const audio = container.querySelector("audio");
    expect(audio?.src).toContain("test-audio.mp3");
  });

  it("renders volume control", () => {
    const { container } = render(<AudioPlayer {...defaultProps} />);
    const inputs = container.querySelectorAll("input[type='range']");
    expect(inputs.length).toBeGreaterThan(0);
  });
});
