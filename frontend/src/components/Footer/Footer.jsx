import React from 'react';
import styles from './Footer.module.css';

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.brandBlock}>
          <div className={styles.logo} aria-label="Логотип проекта" role="img">
            <img className={styles.logoImg} src="/logo.png" alt="Логотип проекта" />
          </div>
          <p className={styles.subtitle}>
            Генеративный ИИ, превращающий данные из файлов в TypeScript
          </p>
        </div>

        <a className={styles.contactButton} href="https://syharik.ru">
          Связаться с нами
        </a>
      </div>

      <div className={styles.bottom}>
        <p className={styles.copyright}>© 2026 SyharikTS. Все права защищены.</p>
        <p className={styles.note}>
          Проект разработан на Форуме программных разработчиков Ростова-на-Дону
          «Хакатон Весна 2026» командой «42x САУ» по <a href="https://drive.localzet.com/share/Mu9jI6h1lMEU4Q6N/direct">мотиву кейса</a> компании ПАО «Сбербанк».
        </p>
      </div>
    </footer>
  );
}

