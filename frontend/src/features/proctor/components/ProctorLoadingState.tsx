type ProctorLoadingStateProps = {
  message: string;
};

export function ProctorLoadingState({ message }: ProctorLoadingStateProps) {
  return <p className="muted">{message}</p>;
}
