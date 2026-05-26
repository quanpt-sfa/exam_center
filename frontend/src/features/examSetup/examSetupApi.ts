export * from './api/contracts';
export * from './api/examAuthoringApi';
export * from './api/deliverySetupApi';

import type { ExamSetupBaseData } from './api/contracts';
import { loadExamAuthoringBaseData } from './api/examAuthoringApi';
import { loadDeliverySetupBaseData } from './api/deliverySetupApi';

export async function loadExamSetupBaseData(): Promise<ExamSetupBaseData> {
  const [authoringData, deliveryData] = await Promise.all([
    loadExamAuthoringBaseData(),
    loadDeliverySetupBaseData(),
  ]);

  return {
    exams: authoringData.exams,
    classSections: authoringData.classSections,
    assessmentTypes: authoringData.assessmentTypes,
    rooms: deliveryData.rooms,
    stations: deliveryData.stations,
    students: deliveryData.students,
    instructors: deliveryData.instructors,
    modules: deliveryData.modules,
  };
}