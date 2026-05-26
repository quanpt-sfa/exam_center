export type LoginHeroVisual =
  | {
      type: 'exam-illustration';
      timerText: string;
      scoreText: string;
    }
  | {
      type: 'image';
      src: string;
      alt: string;
    };

export type LoginPageContent = {
  brand: {
    initials: string;
    name: string;
    logoImageSrc?: string;
    logoAlt: string;
  };
  hero: {
    eyebrow: string;
    title: string;
    description: string;
    visual: LoginHeroVisual;
  };
  form: {
    eyebrow: string;
    title: string;
    identifierLabel: string;
    identifierPlaceholder: string;
    passwordLabel: string;
    passwordPlaceholder: string;
    showPasswordLabel: string;
    hidePasswordLabel: string;
    submitLabel: string;
    submittingLabel: string;
    genericError: string;
  };
  frame: {
    footerText: string;
  };
};

export const loginPageContent: LoginPageContent = {
  brand: {
    initials: 'ES',
    name: 'Exam Sys',
    logoAlt: 'Exam Sys logo',
  },
  hero: {
    eyebrow: 'Exam Sys',
    title: 'H\u1ec7 th\u1ed1ng thi v\u00e0 ch\u1ea5m \u0111i\u1ec3m',
    description:
      '\u0110\u0103ng nh\u1eadp \u0111\u1ec3 v\u00e0o khu v\u1ef1c qu\u1ea3n tr\u1ecb, coi thi ho\u1eb7c l\u00e0m b\u00e0i theo quy\u1ec1n t\u00e0i kho\u1ea3n.',
    visual: {
      type: 'exam-illustration',
      timerText: '45:00',
      scoreText: 'A+',
    },
  },
  form: {
    eyebrow: '\u0110\u0103ng nh\u1eadp',
    title: 'Ch\u00e0o m\u1eebng tr\u1edf l\u1ea1i',
    identifierLabel: 'T\u00e0i kho\u1ea3n ho\u1eb7c email',
    identifierPlaceholder: 'Nh\u1eadp t\u00e0i kho\u1ea3n',
    passwordLabel: 'M\u1eadt kh\u1ea9u',
    passwordPlaceholder: 'Nh\u1eadp m\u1eadt kh\u1ea9u',
    showPasswordLabel: 'Hi\u1ec7n m\u1eadt kh\u1ea9u',
    hidePasswordLabel: '\u1ea8n m\u1eadt kh\u1ea9u',
    submitLabel: '\u0110\u0103ng nh\u1eadp',
    submittingLabel: '\u0110ang \u0111\u0103ng nh\u1eadp...',
    genericError: 'Kh\u00f4ng th\u1ec3 \u0111\u0103ng nh\u1eadp. Vui l\u00f2ng th\u1eed l\u1ea1i.',
  },
  frame: {
    footerText: 'Vi\u1ec7n T\u00e0i ch\u00ednh - K\u1ebf to\u00e1n',
  },
};
