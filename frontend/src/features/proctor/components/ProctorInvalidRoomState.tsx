import { Link } from 'react-router-dom';

type ProctorInvalidRoomStateProps = {
  message: string;
};

export function ProctorInvalidRoomState({ message }: ProctorInvalidRoomStateProps) {
  return (
    <div className="card" style={{ borderColor: 'var(--clr-danger-light)' }}>
      <h3>Không mở được phòng thi</h3>
      <p className="error">{message}</p>
      <Link className="secondary-button" to="/proctor/sittings">
        Quay lại danh sách phòng
      </Link>
    </div>
  );
}