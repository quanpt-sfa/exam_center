import { Link } from 'react-router-dom';

type ProctorRoomHeaderProps = {
  roomCode: string;
  title: string;
  subtitle: string;
  examSittingRoomId?: number | null;
};

export function ProctorRoomHeader({ roomCode, title, subtitle, examSittingRoomId }: ProctorRoomHeaderProps) {
  return (
    <div className="section-heading">
      <div>
        <p className="eyebrow">Proctor Portal</p>
        <h2>{title}</h2>
        <p className="muted">{subtitle}</p>
      </div>
      <div style={{ display: 'flex', gap: 'var(--sp-2)', flexWrap: 'wrap' }}>
        <Link className="secondary-button" to="/proctor/sittings">
          Tất cả phòng
        </Link>
        {examSittingRoomId ? (
          <Link className="secondary-button" to={`/proctor/sitting-rooms/${examSittingRoomId}`}>
            Không gian {roomCode}
          </Link>
        ) : null}
      </div>
    </div>
  );
}
