export type ProctorRoomIdResolution =
  | { isValid: true; examSittingRoomId: number }
  | { isValid: false; examSittingRoomId: null; errorMessage: string };

export function resolveExamSittingRoomId(rawValue?: string): ProctorRoomIdResolution {
  const value = String(rawValue ?? '').trim();
  if (!/^[1-9]\d*$/.test(value)) {
    return {
      isValid: false,
      examSittingRoomId: null,
      errorMessage: 'Mã phòng thi không hợp lệ. Vui lòng quay lại danh sách phòng được phân công.',
    };
  }

  return {
    isValid: true,
    examSittingRoomId: Number(value),
  };
}