<?php
/**
 * ⚡ RONY PC TELEGRAM CONTROL BOT (HOSTING SERVER + LOCAL AGENT BRIDGE) ⚡
 * Розміщується на хостингу (driver.lutsk.ua).
 * Приймає Webhook від Telegram та передає команди на локальний ПК через агента.
 */

date_default_timezone_set('Europe/Kiev');

// Load environment variables from .env file
function loadEnv($path = __DIR__ . '/.env') {
    if (!file_exists($path)) {
        return;
    }
    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        $line = trim($line);
        if ($line === '' || strpos($line, '#') === 0) continue;
        list($name, $value) = explode('=', $line, 2);
        $name = trim($name);
        $value = trim($value);
        if (!array_key_exists($name, $_SERVER) && !array_key_exists($name, $_ENV)) {
            putenv(sprintf('%s=%s', $name, $value));
            $_ENV[$name] = $value;
            $_SERVER[$name] = $value;
        }
    }
}

loadEnv();

$BOT_TOKEN = getenv('BOT_TOKEN') ?: '8733735106:AAGqTa-GtALehba8nXfLeNikcBjxLX9r6TM';
$PC_NAME = getenv('PC_NAME') ?: 'Rony';
$PC_IP = getenv('PC_IP') ?: '192.168.1.166';
$PUBLIC_IP = getenv('PUBLIC_IP') ?: ''; // Публічний IP / DDNS домашнього роутера
$PC_MAC = getenv('PC_MAC') ?: 'A0:AD:9F:07:26:40';
$PC_PORT = (int)(getenv('PC_PORT') ?: 9);
$YT_MUSIC_URL = getenv('YT_MUSIC_URL') ?: 'https://music.youtube.com/watch?v=1rXJbd3I2W4&list=RDAMVMn6P0SitRwy8';

$allowedUsersStr = getenv('ALLOWED_USERS') ?: '761584410';
$allowedUsers = array_filter(array_map('trim', explode(',', $allowedUsersStr)));

$LOG_FILE = __DIR__ . '/activity.log';
$QUEUE_FILE = __DIR__ . '/queue.json';
$PCS_FILE = __DIR__ . '/pcs.json';
$USER_PCS_FILE = __DIR__ . '/user_pcs.json';
$LAST_MENU_FILE = __DIR__ . '/last_menu.json';
$SEARCH_STATE_FILE = __DIR__ . '/search_state.json';

// Ensure default PC exists in database
function getPcsData() {
    global $PCS_FILE, $PC_NAME, $PC_IP, $PC_MAC, $PC_PORT;
    $pcs = [];
    if (file_exists($PCS_FILE)) {
        $pcs = json_decode(file_get_contents($PCS_FILE), true) ?: [];
    }
    if (empty($pcs)) {
        $pcs['pc_default'] = [
            'id' => 'pc_default',
            'name' => $PC_NAME ?: 'Rony PC',
            'ip' => $PC_IP ?: '192.168.1.166',
            'mac' => $PC_MAC ?: 'A0:AD:9F:07:26:40',
            'port' => $PC_PORT ?: 9,
            'last_seen' => time(),
            'last_seen_date' => date('Y-m-d H:i:s')
        ];
        file_put_contents($PCS_FILE, json_encode($pcs, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    }
    return $pcs;
}

function savePcsData($pcs) {
    global $PCS_FILE;
    file_put_contents($PCS_FILE, json_encode($pcs, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
}

function deletePcData($pcId) {
    $pcs = getPcsData();
    if (isset($pcs[$pcId])) {
        unset($pcs[$pcId]);
        savePcsData($pcs);
        return true;
    }
    return false;
}

function getSelectedPcId($chatId) {
    global $USER_PCS_FILE;
    $userPcs = [];
    if (file_exists($USER_PCS_FILE)) {
        $userPcs = json_decode(file_get_contents($USER_PCS_FILE), true) ?: [];
    }
    $pcs = getPcsData();
    $selected = $userPcs[(string)$chatId] ?? null;
    if (!$selected || !isset($pcs[$selected])) {
        // Default to first available PC
        $keys = array_keys($pcs);
        $selected = $keys[0] ?? 'pc_default';
        setSelectedPcId($chatId, $selected);
    }
    return $selected;
}

function setSelectedPcId($chatId, $pcId) {
    global $USER_PCS_FILE;
    $userPcs = [];
    if (file_exists($USER_PCS_FILE)) {
        $userPcs = json_decode(file_get_contents($USER_PCS_FILE), true) ?: [];
    }
    $userPcs[(string)$chatId] = $pcId;
    file_put_contents($USER_PCS_FILE, json_encode($userPcs, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
}

function updatePcHeartbeat($pcId, $pcName = null, $ip = null, $mac = null) {
    $pcs = getPcsData();
    if (!isset($pcs[$pcId])) {
        $pcs[$pcId] = [
            'id' => $pcId,
            'name' => $pcName ?: ("ПК " . strtoupper($pcId)),
            'ip' => $ip ?: 'Dynamic',
            'mac' => $mac ?: 'Dynamic',
            'port' => 9
        ];
    }
    if ($pcName) $pcs[$pcId]['name'] = $pcName;
    if ($ip) $pcs[$pcId]['ip'] = $ip;
    if ($mac) $pcs[$pcId]['mac'] = $mac;

    $pcs[$pcId]['last_seen'] = time();
    $pcs[$pcId]['last_seen_date'] = date('Y-m-d H:i:s');
    savePcsData($pcs);
}

function getSinglePcStatus($pcId) {
    $pcs = getPcsData();
    if (isset($pcs[$pcId])) {
        $isOnline = (time() - ($pcs[$pcId]['last_seen'] ?? 0)) < 15;
        return [
            'id' => $pcId,
            'name' => $pcs[$pcId]['name'] ?? 'ПК',
            'ip' => $pcs[$pcId]['ip'] ?? '',
            'mac' => $pcs[$pcId]['mac'] ?? '',
            'port' => $pcs[$pcId]['port'] ?? 9,
            'online' => $isOnline,
            'last_seen_date' => $pcs[$pcId]['last_seen_date'] ?? 'Ніколи'
        ];
    }
    return ['id' => $pcId, 'name' => 'Невідомий ПК', 'online' => false, 'last_seen_date' => 'Ніколи'];
}

function getSearchState($chatId) {
    global $SEARCH_STATE_FILE;
    if (file_exists($SEARCH_STATE_FILE)) {
        $data = json_decode(file_get_contents($SEARCH_STATE_FILE), true);
        return is_array($data) ? (!empty($data[(string)$chatId])) : false;
    }
    return false;
}

function setSearchState($chatId, $active) {
    global $SEARCH_STATE_FILE;
    $data = [];
    if (file_exists($SEARCH_STATE_FILE)) {
        $data = json_decode(file_get_contents($SEARCH_STATE_FILE), true) ?: [];
    }
    $data[(string)$chatId] = (bool)$active;
    file_put_contents($SEARCH_STATE_FILE, json_encode($data));
}

function getLastMenuId($chatId) {
    global $LAST_MENU_FILE;
    if (file_exists($LAST_MENU_FILE)) {
        $data = json_decode(file_get_contents($LAST_MENU_FILE), true);
        return is_array($data) ? ($data[(string)$chatId] ?? null) : null;
    }
    return null;
}

function setLastMenuId($chatId, $msgId) {
    global $LAST_MENU_FILE;
    $data = [];
    if (file_exists($LAST_MENU_FILE)) {
        $data = json_decode(file_get_contents($LAST_MENU_FILE), true) ?: [];
    }
    $data[(string)$chatId] = $msgId;
    file_put_contents($LAST_MENU_FILE, json_encode($data));
}

function deleteMessageSafely($chatId, $msgId) {
    if ($chatId && $msgId) {
        @telegramApi('deleteMessage', ['chat_id' => $chatId, 'message_id' => $msgId]);
    }
}

function logAction($userId, $username, $action, $status = "SUCCESS") {
    global $LOG_FILE;
    $time = date('Y-m-d H:i:s');
    $log = "[$time] User ID: $userId (@$username) -> Action: $action | Status: $status\n";
    file_put_contents($LOG_FILE, $log, FILE_APPEND);
}

// Atomic thread-safe queue management with flock (filtered by PC ID)
function addCommandToQueue($command, $chatId, $params = [], $pcId = null) {
    global $QUEUE_FILE;
    if (!$pcId) {
        $pcId = getSelectedPcId($chatId);
    }
    $item = [
        'id' => uniqid('cmd_') . '_' . microtime(true),
        'pc_id' => $pcId,
        'command' => $command,
        'chat_id' => $chatId,
        'params' => $params,
        'time' => time()
    ];

    $fp = fopen($QUEUE_FILE, 'c+');
    if ($fp && flock($fp, LOCK_EX)) {
        $size = filesize($QUEUE_FILE);
        $queue = [];
        if ($size > 0) {
            rewind($fp);
            $content = fread($fp, $size);
            $queue = json_decode($content, true) ?: [];
        }
        $queue[] = $item;
        ftruncate($fp, 0);
        rewind($fp);
        fwrite($fp, json_encode(array_values($queue), JSON_PRETTY_PRINT));
        fflush($fp);
        flock($fp, LOCK_UN);
        fclose($fp);
    }
    return $item['id'];
}

function popAllQueueItems($pcId = 'pc_default') {
    global $QUEUE_FILE;
    $result = [];
    if (!file_exists($QUEUE_FILE)) return [];
    $fp = fopen($QUEUE_FILE, 'c+');
    if ($fp && flock($fp, LOCK_EX)) {
        $size = filesize($QUEUE_FILE);
        $remaining = [];
        if ($size > 0) {
            rewind($fp);
            $content = fread($fp, $size);
            $queue = json_decode($content, true) ?: [];
            foreach ($queue as $item) {
                $itemPc = $item['pc_id'] ?? 'pc_default';
                if ($itemPc === $pcId) {
                    $result[] = $item;
                } else {
                    $remaining[] = $item;
                }
            }
        }
        ftruncate($fp, 0);
        rewind($fp);
        fwrite($fp, json_encode(array_values($remaining), JSON_PRETTY_PRINT));
        fflush($fp);
        flock($fp, LOCK_UN);
        fclose($fp);
    }
    return $result;
}

function isAllowed($userId) {
    global $allowedUsers;
    if (empty($allowedUsers)) return true;
    return in_array((string)$userId, array_map('strval', $allowedUsers));
}

function telegramApi($method, $data = []) {
    global $BOT_TOKEN;
    $url = "https://api.telegram.org/bot{$BOT_TOKEN}/{$method}";
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 60);
    $response = curl_exec($ch);
    curl_close($ch);
    
    return json_decode($response, true);
}

function sendTelegramPhoto($chatId, $filePath, $caption = "") {
    global $BOT_TOKEN;
    $url = "https://api.telegram.org/bot{$BOT_TOKEN}/sendPhoto";
    
    $ch = curl_init();
    $cfile = new CURLFile($filePath, 'image/png', 'screenshot.png');
    $postData = [
        'chat_id' => $chatId,
        'photo' => $cfile,
        'caption' => $caption,
        'parse_mode' => 'Markdown',
        'reply_markup' => json_encode(getMainKeyboard($chatId))
    ];
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $postData);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $res = curl_exec($ch);
    curl_close($ch);
    return json_decode($res, true);
}

function sendWakeOnLan($mac, $ip = '255.255.255.255', $port = 9) {
    $macHex = str_replace([':', '-'], '', $mac);
    if (strlen($macHex) !== 12) return false;
    $binaryMac = hex2bin($macHex);
    $packet = str_repeat("\xFF", 6) . str_repeat($binaryMac, 16);
    
    $targets = array_unique([$ip, '255.255.255.255', '192.168.1.255', '192.168.1.166']);
    $ports = [$port, 7, 9];

    $success = false;
    foreach ($targets as $targetIp) {
        if (empty($targetIp)) continue;
        foreach ($ports as $p) {
            $sock = @socket_create(AF_INET, SOCK_DGRAM, SOL_UDP);
            if ($sock) {
                @socket_set_option($sock, SOL_SOCKET, SO_BROADCAST, 1);
                if (@socket_sendto($sock, $packet, strlen($packet), 0, $targetIp, $p)) {
                    $success = true;
                }
                @socket_close($sock);
            }
        }
    }
    return $success;
}

// Keyboards
function getMainKeyboard($chatId = null) {
    $pcId = $chatId ? getSelectedPcId($chatId) : 'pc_default';
    $pcSt = getSinglePcStatus($pcId);
    $stIcon = $pcSt['online'] ? '🟢 ONLINE' : '🔴 OFFLINE';
    $pcName = $pcSt['name'] ?? 'ПК';

    return [
        'inline_keyboard' => [
            [
                ['text' => "📊 Стан ПК ($stIcon)", 'callback_data' => 'menu_status'],
                ['text' => '📸 Скріншот', 'callback_data' => 'menu_screenshot']
            ],
            [
                ['text' => '📱 Активні процеси', 'callback_data' => 'menu_processes'],
                ['text' => '🌐 Вкладки Браузера', 'callback_data' => 'menu_browser']
            ],
            [
                ['text' => '🎵 Меню Музика', 'callback_data' => 'menu_music'],
                ['text' => '🎬 Меню Фільми / Серіали', 'callback_data' => 'menu_movies']
            ],
            [
                ['text' => '🚀 Програми', 'callback_data' => 'menu_apps'],
                ['text' => '⚙️ Живлення', 'callback_data' => 'menu_power']
            ],
            [
                ['text' => '🔊 Пристрої звуку', 'callback_data' => 'menu_audio']
            ],
            [
                ['text' => '🌐 Мережа & Інфо', 'callback_data' => 'menu_net'],
                ['text' => '📜 Логи дій', 'callback_data' => 'menu_logs']
            ],
            [
                ['text' => "🖥️ Обрано: {$pcName} (Змінити ПК)", 'callback_data' => 'menu_select_pc']
            ],
            [
                ['text' => '🔄 Оновити статус', 'callback_data' => 'menu_main']
            ]
        ]
    ];
}

function getPcsListKeyboard() {
    $pcs = getPcsData();
    $rows = [];
    foreach ($pcs as $id => $pc) {
        $isOnline = (time() - ($pc['last_seen'] ?? 0)) < 15;
        $badge = $isOnline ? '🟢 ONLINE' : '🔴 OFFLINE';
        $rows[] = [
            ['text' => "🖥️ {$pc['name']} ({$badge})", 'callback_data' => "select_pc_{$id}"],
            ['text' => "🗑️ Видалити", 'callback_data' => "delete_pc_ask_{$id}"]
        ];
    }
    $rows[] = [
        ['text' => '➕ Додати новий ПК', 'callback_data' => 'add_pc_prompt']
    ];
    $rows[] = [
        ['text' => '« Назад у меню', 'callback_data' => 'menu_main']
    ];
    return ['inline_keyboard' => $rows];
}

function getBrowserKeyboard() {
    return [
        'inline_keyboard' => [
            [
                ['text' => '⬅️ Вліво', 'callback_data' => 'browser_prev_tab'],
                ['text' => '➡️ Вправо', 'callback_data' => 'browser_next_tab']
            ],
            [
                ['text' => '➕ Нова вкладка', 'callback_data' => 'browser_new_tab'],
                ['text' => '❌ Закрити вкладку', 'callback_data' => 'browser_close_tab']
            ],
            [
                ['text' => '🔍 Пошук у браузері', 'callback_data' => 'browser_search_prompt']
            ],
            [
                ['text' => '« Назад у головне меню', 'callback_data' => 'menu_main']
            ]
        ]
    ];
}

function getAppsKeyboard() {
    return [
        'inline_keyboard' => [
            [
                ['text' => '☄️ Comet Browser', 'callback_data' => 'app_comet']
            ],
            [
                ['text' => '💬 Discord', 'callback_data' => 'app_discord'],
                ['text' => '🎮 Steam', 'callback_data' => 'app_steam']
            ],
            [
                ['text' => '🎧 YT Music (відкрити в Comet)', 'callback_data' => 'app_ytmusic']
            ],
            [
                ['text' => '« Назад у головне меню', 'callback_data' => 'menu_main']
            ]
        ]
    ];
}

function getMusicKeyboard() {
    return [
        'inline_keyboard' => [
            [
                ['text' => '⏮️ Попередній трек', 'callback_data' => 'media_music_prev'],
                ['text' => '⏯️ Пауза / Плей', 'callback_data' => 'media_music_play'],
                ['text' => '⏭️ Наступний трек', 'callback_data' => 'media_music_next']
            ],
            [
                ['text' => '🔉 Гучність -', 'callback_data' => 'media_vdown'],
                ['text' => '🔇 Без звуку', 'callback_data' => 'media_mute'],
                ['text' => '🔊 Гучність +', 'callback_data' => 'media_vup']
            ],
            [
                ['text' => '🎧 Відкрити YouTube Music (Comet)', 'callback_data' => 'app_ytmusic']
            ],
            [
                ['text' => '« Назад у головне меню', 'callback_data' => 'menu_main']
            ]
        ]
    ];
}

function getMoviesKeyboard() {
    return [
        'inline_keyboard' => [
            [
                ['text' => '⏪ Перемотка 5 сек', 'callback_data' => 'media_rewind'],
                ['text' => '⏯️ Пауза / Плей', 'callback_data' => 'media_play'],
                ['text' => '⏩ Перемотка 5 сек', 'callback_data' => 'media_forward']
            ],
            [
                ['text' => '🔼 Скрол вгору', 'callback_data' => 'media_scroll_up'],
                ['text' => '🔽 Скрол вниз', 'callback_data' => 'media_scroll_down']
            ],
            [
                ['text' => '🔉 Гучність -', 'callback_data' => 'media_vdown'],
                ['text' => '🔇 Без звуку', 'callback_data' => 'media_mute'],
                ['text' => '🔊 Гучність +', 'callback_data' => 'media_vup']
            ],
            [
                ['text' => '🖥️ Повний екран (F)', 'callback_data' => 'media_fullscreen']
            ],
            [
                ['text' => '« Назад у головне меню', 'callback_data' => 'menu_main']
            ]
        ]
    ];
}

function getPowerKeyboard() {
    return [
        'inline_keyboard' => [
            [
                ['text' => '🔴 Вимкнути ПК (Shutdown)', 'callback_data' => 'power_shutdown'],
                ['text' => '🌙 Режим сну (Sleep)', 'callback_data' => 'power_sleep']
            ],
            [
                ['text' => '🔄 Перезавантажити (Reboot)', 'callback_data' => 'power_reboot']
            ],
            [
                ['text' => '🔒 Заблокувати екран', 'callback_data' => 'power_lock'],
                ['text' => '🔑 Розблокувати екран', 'callback_data' => 'power_unlock']
            ],
            [
                ['text' => '« Назад у головне меню', 'callback_data' => 'menu_main']
            ]
        ]
    ];
}

function getAudioDevicesKeyboard($devices = []) {
    $rows = [];
    $defaultName = '';

    if (empty($devices)) {
        $rows[] = [
            ['text' => '⏳ Немає даних про пристрої', 'callback_data' => 'menu_audio']
        ];
    } else {
        foreach ($devices as $idx => $dev) {
            $name = $dev['name'] ?? ('Пристрій ' . ($idx + 1));
            $name = str_replace(["\n", "\r"], ' ', $name);
            $isDefault = !empty($dev['is_default']);
            $deviceIndex = isset($dev['index']) ? (int)$dev['index'] : (int)$idx;
            $mark = $isDefault ? '✅' : '❌';
            if ($isDefault) {
                $defaultName = $name;
            }
            $btnTitle = (mb_strlen($name) > 28) ? (mb_substr($name, 0, 25) . '...') : $name;
            $rows[] = [
                ['text' => "{$mark} {$btnTitle}", 'callback_data' => "select_audio_{$deviceIndex}"]
            ];
        }
    }

    $rows[] = [
        ['text' => '🔄 Оновити список', 'callback_data' => 'menu_audio'],
        ['text' => '« Головне меню', 'callback_data' => 'menu_main']
    ];

    return [
        'inline_keyboard' => $rows,
        'default_name' => $defaultName
    ];
}

function renderAudioDevicesMenu($devices = []) {
    $kbData = getAudioDevicesKeyboard($devices);
    $defaultName = $kbData['default_name'] ?? '';
    unset($kbData['default_name']);

    $text = "🔊 *ПРИСТРОЇ ВИВЕДЕННЯ ЗВУКУ*\n"
          . "───────────────────────────\n";

    if (empty($devices)) {
        $text .= "Не знайдено активних пристроїв виведення.\n";
    } else {
        if ($defaultName !== '') {
            $safeDefault = str_replace(['*', '_', '`', '['], '', $defaultName);
            $text .= "Активний: *{$safeDefault}* ✅\n\n";
        } else {
            $text .= "Оберіть пристрій нижче.\n\n";
        }
        $text .= "✅ — активний пристрій\n"
               . "❌ — неактивний\n\n"
               . "Натисніть на пристрій, щоб зробити його активним.";
    }

    return [
        'text' => $text,
        'keyboard' => $kbData
    ];
}

function editOrSendMessage($chatId, $messageId, $text, $keyboard = null) {
    $params = [
        'chat_id' => $chatId,
        'text' => $text,
        'parse_mode' => 'Markdown'
    ];
    if ($keyboard) {
        $params['reply_markup'] = $keyboard;
    }
    
    // First attempt editMessageText if messageId exists
    if ($messageId) {
        $params['message_id'] = $messageId;
        $res = telegramApi('editMessageText', $params);
        if (isset($res['ok']) && $res['ok'] === true) {
            setLastMenuId($chatId, $messageId);
            return $res;
        }
    }
    
    // If edit failed (e.g. previous message was a Photo screenshot or deleted),
    // delete previous message and send new text message so ONLY 1 MESSAGE exists!
    $oldMenuId = getLastMenuId($chatId);
    deleteMessageSafely($chatId, $oldMenuId);
    if ($messageId && $messageId != $oldMenuId) {
        deleteMessageSafely($chatId, $messageId);
    }
    
    unset($params['message_id']);
    $newRes = telegramApi('sendMessage', $params);
    if (isset($newRes['result']['message_id'])) {
        setLastMenuId($chatId, $newRes['result']['message_id']);
    }
    return $newRes;
}

// -------------------------------------------------------------------
// API ENDPOINTS FOR LOCAL AGENT RUNNING ON PC (pc_agent/agent.py)
// -------------------------------------------------------------------

// 1. Agent Poll: Agent asks for pending commands
if (isset($_GET['agent_poll'])) {
    header('Content-Type: application/json');
    $pcId = $_GET['pc_id'] ?? 'pc_default';
    $pcName = $_GET['pc_name'] ?? null;
    $ip = $_GET['ip'] ?? null;
    $mac = $_GET['mac'] ?? null;
    updatePcHeartbeat($pcId, $pcName, $ip, $mac);
    $queue = popAllQueueItems($pcId);
    echo json_encode(['commands' => $queue]);
    exit;
}

// 2. Agent Heartbeat / Startup Notification: PC turned on!
if (isset($_GET['agent_online']) || isset($_POST['agent_online'])) {
    header('Content-Type: application/json');
    $pcId = $_REQUEST['pc_id'] ?? 'pc_default';
    $pcName = $_REQUEST['pc_name'] ?? $PC_NAME;
    $ip = $_REQUEST['ip'] ?? null;
    $mac = $_REQUEST['mac'] ?? null;
    updatePcHeartbeat($pcId, $pcName, $ip, $mac);

    if (!empty($allowedUsers)) {
        foreach ($allowedUsers as $uid) {
            $oldMenuId = getLastMenuId($uid);
            deleteMessageSafely($uid, $oldMenuId);

            $res = telegramApi('sendMessage', [
                'chat_id' => $uid,
                'text' => "🟢 *ПК онлайн!* Комп'ютер `{$pcName}` увімкнувся та готовий до роботи.",
                'parse_mode' => 'Markdown',
                'reply_markup' => getMainKeyboard($uid)
            ]);
            if (isset($res['result']['message_id'])) {
                setLastMenuId($uid, $res['result']['message_id']);
            }
        }
    }
    echo json_encode(['status' => 'ok']);
    exit;
}

// 3. Agent Result: Agent responds with screenshot photo or status text
if (isset($_POST['agent_result'])) {
    header('Content-Type: application/json');
    $pcId = $_POST['pc_id'] ?? 'pc_default';
    updatePcHeartbeat($pcId);
    $chatId = $_POST['chat_id'] ?? '';
    $text = $_POST['text'] ?? '';
    $targetMsgId = $_POST['msg_id'] ?? null;
    
    if ($chatId) {
        if (isset($_POST['type']) && $_POST['type'] === 'processes' && isset($_POST['procs_json'])) {
            $procs = json_decode($_POST['procs_json'], true) ?: [];
            
            $page = isset($_POST['page']) ? (int)$_POST['page'] : 1;
            $perPage = 10;
            $totalProcs = count($procs);
            $totalPages = ceil($totalProcs / $perPage);
            if ($page < 1) $page = 1;
            if ($page > $totalPages && $totalPages > 0) $page = $totalPages;

            $procText = "📱 *АКТИВНІ ПРОЦЕСИ ПК* ({$totalProcs})\n"
                      . "───────────────────────────\n";
            $buttons = [];
            
            if (empty($procs)) {
                $procText .= "Не знайдено активних процесів.\n";
            } else {
                $startIdx = ($page - 1) * $perPage;
                $pageProcs = array_slice($procs, $startIdx, $perPage);
                
                foreach ($pageProcs as $idx => $p) {
                    $num = $startIdx + $idx + 1;
                    $rawTitle = $p['title'] ?? $p['name'];
                    $cleanTitle = mb_substr(preg_replace('/[*_`\[\]\\\\]/', '', $rawTitle), 0, 30);
                    $cleanName = preg_replace('/[*_`\[\]\\\\]/', '', $p['name']);
                    $pid = (int)$p['pid'];
                    $procText .= "{$num}. 🔹 *{$cleanTitle}* (`{$cleanName}`)\n";
                    
                    $btnTitle = (mb_strlen($cleanTitle) > 15) ? mb_substr($cleanTitle, 0, 15) . '...' : $cleanTitle;
                    $buttons[] = [['text' => "❌ {$btnTitle} (PID {$pid})", 'callback_data' => "kill_proc_{$pid}_{$page}"]];
                }
            }
            $procText .= "───────────────────────────\n"
                       . "Сторінка {$page} з " . max(1, $totalPages) . "\n"
                       . "Оберіть задачу нижче для примусового закриття:";
            
            $navRow = [];
            if ($page > 1) {
                $navRow[] = ['text' => '⬅️ Назад', 'callback_data' => "menu_processes_" . ($page - 1)];
            }
            if ($page < $totalPages) {
                $navRow[] = ['text' => 'Вперед ➡️', 'callback_data' => "menu_processes_" . ($page + 1)];
            }
            if (!empty($navRow)) {
                $buttons[] = $navRow;
            }
            
            $buttons[] = [
                ['text' => '🔄 Оновити список', 'callback_data' => "menu_processes_{$page}"],
                ['text' => '« Головне меню', 'callback_data' => 'menu_main']
            ];
            
            $msgIdToEdit = $targetMsgId ?: getLastMenuId($chatId);
            $res = editOrSendMessage($chatId, $msgIdToEdit, $procText, ['inline_keyboard' => $buttons]);
            if (isset($res['result']['message_id'])) {
                setLastMenuId($chatId, $res['result']['message_id']);
            }
        } else if (isset($_POST['type']) && $_POST['type'] === 'audio_devices' && isset($_POST['audio_devices_json'])) {
            $devices = json_decode($_POST['audio_devices_json'], true) ?: [];
            $menu = renderAudioDevicesMenu($devices);
            $oldMenuId = getLastMenuId($chatId);
            $res = editOrSendMessage($chatId, $oldMenuId, $menu['text'], $menu['keyboard']);
            if (isset($res['result']['message_id'])) {
                setLastMenuId($chatId, $res['result']['message_id']);
            }
        } else if (isset($_FILES['screenshot']) && $_FILES['screenshot']['error'] === UPLOAD_ERR_OK) {
            $caption = "📸 *Скріншот екрана ПК RONY*\n"
                . "───────────────────────────\n"
                . "⏱️ Оновлено: `" . date('H:i:s') . "`";
            
            // Delete old text/photo menu message so new screenshot replaces it cleanly!
            $oldMenuId = getLastMenuId($chatId);
            deleteMessageSafely($chatId, $oldMenuId);
            if ($targetMsgId && $targetMsgId != $oldMenuId) {
                deleteMessageSafely($chatId, $targetMsgId);
            }

            $res = sendTelegramPhoto($chatId, $_FILES['screenshot']['tmp_name'], $caption);
            if (isset($res['result']['message_id'])) {
                setLastMenuId($chatId, $res['result']['message_id']);
            }
        } else if ($text && strpos($text, '📊') === 0) {
            // Edit status into current menu message
            $oldMenuId = getLastMenuId($chatId);
            editOrSendMessage($chatId, $oldMenuId, $text, getMainKeyboard($chatId));
        }
    }
    echo json_encode(['status' => 'ok']);
    exit;
}

// -------------------------------------------------------------------
// TELEGRAM WEBHOOK UPDATE HANDLER
// -------------------------------------------------------------------

function handleUpdate($update) {
    global $PC_NAME, $PC_IP, $PUBLIC_IP, $PC_MAC, $PC_PORT, $YT_MUSIC_URL, $LOG_FILE;

    if (isset($update['message'])) {
        $msg = $update['message'];
        $chatId = $msg['chat']['id'];
        $userId = $msg['from']['id'];
        $username = $msg['from']['username'] ?? 'Unknown';
        $text = trim($msg['text'] ?? '');

        if (!isAllowed($userId)) {
            telegramApi('sendMessage', [
                'chat_id' => $chatId,
                'text' => "⛔ Access Denied! Ваш Telegram ID ($userId) не авторизовано."
            ]);
            logAction($userId, $username, "Unauthorized: $text", "BLOCKED");
            return;
        }

        // Режим пошуку: лише ОДНЕ наступне текстове повідомлення після кнопки 🔍
        // Команди бота (/start тощо) не вважаються пошуковим запитом
        if (getSearchState($chatId)) {
            if ($text !== '' && strpos($text, '/') !== 0) {
                setSearchState($chatId, false);
                logAction($userId, $username, "Web search for: $text");
                addCommandToQueue('browser_search', $chatId, [
                    'query' => $text,
                    'open_first_result' => true
                ]);

                $oldMenuId = getLastMenuId($chatId);
                editOrSendMessage(
                    $chatId,
                    $oldMenuId,
                    "🔍 *Пошук у браузері:*\nНадіслано запит: `{$text}`\nВідкриваю перший не рекламний результат...",
                    getBrowserKeyboard()
                );
                return;
            }
            // Якщо надіслали команду — виходимо з режиму пошуку і обробляємо далі
            setSearchState($chatId, false);
        }

        if ($text === '/start' || $text === '/menu') {
            logAction($userId, $username, "/start menu");
            setSearchState($chatId, false);
            $oldMenuId = getLastMenuId($chatId);
            deleteMessageSafely($chatId, $oldMenuId);

            $pcId = getSelectedPcId($chatId);
            $st = getSinglePcStatus($pcId);
            $statusStr = $st['online'] ? "🟢 *ПК Онлайн* (Агент підключено)" : "🔴 *ПК Офлайн*";
            
            $caption = "⚡ *RONY PC CONTROL CENTER* ⚡\n"
                . "───────────────────────────\n"
                . "🖥️ *Комп'ютер:* {$st['name']}\n"
                . "📡 *Статус:* {$statusStr}\n"
                . "🌐 *IP:* `" . ($st['ip'] ?? '') . "`\n"
                . "📟 *MAC:* `" . ($st['mac'] ?? '') . "`\n"
                . "───────────────────────────\n"
                . "Оберіть потрібну дію з меню нижче:";

            $res = telegramApi('sendMessage', [
                'chat_id' => $chatId,
                'text' => $caption,
                'parse_mode' => 'Markdown',
                'reply_markup' => getMainKeyboard($chatId)
            ]);
            if (isset($res['result']['message_id'])) {
                setLastMenuId($chatId, $res['result']['message_id']);
            }
        } elseif (strpos($text, '/kill') === 0) {
            $parts = explode(' ', $text, 2);
            $target = isset($parts[1]) ? trim($parts[1]) : 'active';
            logAction($userId, $username, "Command /kill: $target");
            if (is_numeric($target)) {
                addCommandToQueue('kill_app', $chatId, ['pid' => (int)$target]);
            } else {
                addCommandToQueue('kill_app', $chatId, ['target' => $target]);
            }
        } elseif (strpos($text, '/msg') === 0) {
            $msgText = trim(substr($text, 4));
            logAction($userId, $username, "Sent message: $msgText");
            addCommandToQueue('msg', $chatId, ['text' => $msgText]);
        } elseif (strpos($text, '/cmd') === 0 || strpos($text, '/run') === 0) {
            $cmd = trim(preg_replace('/^\/(cmd|run)\s*/', '', $text));
            logAction($userId, $username, "Exec CMD: $cmd");
            addCommandToQueue('cmd', $chatId, ['command' => $cmd]);
        } elseif (in_array(strtolower($text), ['wake', '/wake', 'wol', '/wol', 'увімкнути', 'включити', 'увімкнути пк'])) {
            logAction($userId, $username, "Sent WOL via text command: $text");
            $targetIp = $PUBLIC_IP ?: '255.255.255.255';
            sendWakeOnLan($PC_MAC, $targetIp, $PC_PORT);
            $oldMenuId = getLastMenuId($chatId);
            editOrSendMessage($chatId, $oldMenuId, "⚡ *WOL Magic Packet надіслано!*\nНамагаюся ввімкнути ПК `{$PC_NAME}` ({$PC_MAC})...", getPowerKeyboard());
        }
    } elseif (isset($update['callback_query'])) {
        $cb = $update['callback_query'];
        $chatId = $cb['message']['chat']['id'];
        $userId = $cb['from']['id'];
        $username = $cb['from']['username'] ?? 'Unknown';
        $data = $cb['data'];

        if (!isAllowed($userId)) {
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '⛔ Access Denied!']);
            logAction($userId, $username, "CB Unauthorized: $data", "BLOCKED");
            return;
        }

        $msgId = $cb['message']['message_id'] ?? null;

        if ($data === 'menu_main') {
            logAction($userId, $username, "Navigated Main Menu");
            setSearchState($chatId, false);
            $pcId = getSelectedPcId($chatId);
            $st = getSinglePcStatus($pcId);
            $statusStr = $st['online'] ? "🟢 *ПК Онлайн*" : "🔴 *ПК Офлайн*";
            $caption = "⚡ *RONY PC CONTROL CENTER* ⚡\n"
                . "───────────────────────────\n"
                . "🖥️ *Комп'ютер:* {$st['name']}\n"
                . "📡 *Статус:* {$statusStr}\n"
                . "───────────────────────────\n"
                . "Виберіть опцію з меню нижче:";

            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
            editOrSendMessage($chatId, $msgId, $caption, getMainKeyboard($chatId));
        } elseif ($data === 'menu_select_pc') {
            logAction($userId, $username, "Navigated PC Selection Menu");
            setSearchState($chatId, false);
            $pcs = getPcsData();
            $currentPcId = getSelectedPcId($chatId);
            $currentPcName = $pcs[$currentPcId]['name'] ?? $currentPcId;
            $text = "🖥️ *СПИСОК ПІДКТЮЧЕНИХ ПК*\n"
                  . "───────────────────────────\n"
                  . "Поточний обраний ПК: *{$currentPcName}*\n\n"
                  . "Виберіть комп'ютер зі списку нижче для керування ним або додайте новий ПК:";
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
            editOrSendMessage($chatId, $msgId, $text, getPcsListKeyboard());
        } elseif (strpos($data, 'select_pc_') === 0) {
            $targetPcId = str_replace('select_pc_', '', $data);
            setSelectedPcId($chatId, $targetPcId);
            $pcs = getPcsData();
            $targetName = $pcs[$targetPcId]['name'] ?? $targetPcId;
            logAction($userId, $username, "Switched active PC to: $targetPcId");
            telegramApi('answerCallbackQuery', [
                'callback_query_id' => $cb['id'],
                'text' => "✅ Обрано ПК: {$targetName}"
            ]);
            $st = getSinglePcStatus($targetPcId);
            $statusStr = $st['online'] ? "🟢 *ПК Онлайн*" : "🔴 *ПК Офлайн*";
            $caption = "⚡ *RONY PC CONTROL CENTER* ⚡\n"
                . "───────────────────────────\n"
                . "🖥️ *Комп'ютер:* {$st['name']}\n"
                . "📡 *Статус:* {$statusStr}\n"
                . "───────────────────────────\n"
                . "Ви обрали `{$st['name']}`. Всі наступні команди будуть відправлятися на цей ПК.";
            editOrSendMessage($chatId, $msgId, $caption, getMainKeyboard($chatId));
        } elseif (strpos($data, 'delete_pc_ask_') === 0) {
            $targetPcId = str_replace('delete_pc_ask_', '', $data);
            $pcs = getPcsData();
            $targetName = $pcs[$targetPcId]['name'] ?? $targetPcId;
            logAction($userId, $username, "Requested deletion of PC: $targetPcId");
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
            $text = "⚠️ *ПІДТВЕРДЖЕННЯ ВИДАЛЕННЯ ПК*\n"
                  . "───────────────────────────\n"
                  . "Ви впевнені, що хочете видалити ПК *{$targetName}* зі списку?\n\n"
                  . "⚠️ *Зверніть увагу:* Якщо на цьому ПК запущено `agent.py`, він знову з'явиться у списку при наступному опитуванні.";
            $keyboard = [
                'inline_keyboard' => [
                    [
                        ['text' => "✅ Так, видалити {$targetName}", 'callback_data' => "delete_pc_confirm_{$targetPcId}"],
                    ],
                    [
                        ['text' => "❌ Скасувати", 'callback_data' => 'menu_select_pc']
                    ]
                ]
            ];
            editOrSendMessage($chatId, $msgId, $text, $keyboard);
        } elseif (strpos($data, 'delete_pc_confirm_') === 0) {
            $targetPcId = str_replace('delete_pc_confirm_', '', $data);
            $pcs = getPcsData();
            $targetName = $pcs[$targetPcId]['name'] ?? $targetPcId;
            deletePcData($targetPcId);
            logAction($userId, $username, "Deleted PC: $targetPcId ($targetName)");
            telegramApi('answerCallbackQuery', [
                'callback_query_id' => $cb['id'],
                'text' => "🗑️ ПК {$targetName} видалено зі списку"
            ]);
            $text = "🗑️ ПК *{$targetName}* успішно видалено зі списку.\n\nОберіть ПК зі списку нижче:";
            editOrSendMessage($chatId, $msgId, $text, getPcsListKeyboard());
        } elseif ($data === 'add_pc_prompt') {
            logAction($userId, $username, "Requested Add PC Instructions");
            $newPcId = 'pc_' . substr(md5(uniqid(mt_rand(), true)), 0, 6);
            $text = "➕ *ЯК ДОДАТИ НОВИЙ ПК ДО БОТА*\n"
                  . "───────────────────────────\n"
                  . "1️⃣ Скопіюйте папку `pc_agent` або завантажте `agent.py` на новий ПК.\n"
                  . "2️⃣ Відкрийте `agent.py` у текстовому редакторі.\n"
                  . "3️⃣ Вкажіть наступні значення на початку файлу:\n\n"
                  . "```python\n"
                  . "PC_ID = \"{$newPcId}\"\n"
                  . "PC_NAME = \"Новий ПК\"\n"
                  . "```\n\n"
                  . "4️⃣ Запустіть ярлик `Install Rony Agent` на новому ПК (який запускає `install_startup.bat`).\n"
                  . "5️⃣ Бот *автоматично виявить новий ПК* та долучить його до вашого списку!";
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
            editOrSendMessage($chatId, $msgId, $text, getPcsListKeyboard());
        } elseif (strpos($data, 'menu_processes') === 0) {
            $page = 1;
            if (strpos($data, 'menu_processes_') === 0) {
                $page = (int)str_replace('menu_processes_', '', $data);
            }
            logAction($userId, $username, "Checked Active Processes (Page: $page)");
            setSearchState($chatId, false);
            $pcId = getSelectedPcId($chatId);
            $st = getSinglePcStatus($pcId);
            if ($st['online']) {
                addCommandToQueue('get_processes', $chatId, ['msg_id' => $msgId, 'page' => $page]);
                telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '⏳ Отримую список активних процесів...']);
                $loadingText = "📱 *АКТИВНІ ПРОЦЕСИ ПК*\n"
                    . "───────────────────────────\n"
                    . "⏳ *Завантаження списку задач...*\n"
                    . "Зачекайте 1-2 секунди, агент опитує ПК.";
                editOrSendMessage($chatId, $msgId, $loadingText, getMainKeyboard($chatId));
            } else {
                $statusText = "📱 *АКТИВНІ ПРОЦЕСИ ПК*\n"
                    . "───────────────────────────\n"
                    . "🔴 *Статус:* ПК вимкнено або агент офлайн\n"
                    . "⏱️ *Востаннє у мережі:* `" . $st['last_seen_date'] . "`\n";
                telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
                editOrSendMessage($chatId, $msgId, $statusText, getMainKeyboard($chatId));
            }
        } elseif (strpos($data, 'kill_proc_') === 0) {
            $parts = explode('_', str_replace('kill_proc_', '', $data));
            $pid = (int)$parts[0];
            $page = isset($parts[1]) ? (int)$parts[1] : 1;
            logAction($userId, $username, "Kill process PID: $pid");
            addCommandToQueue('kill_app', $chatId, ['pid' => $pid, 'msg_id' => $msgId, 'page' => $page]);
            telegramApi('answerCallbackQuery', [
                'callback_query_id' => $cb['id'],
                'text' => "❌ Закриваю PID {$pid}..."
            ]);
            $loadingText = "📱 *АКТИВНІ ПРОЦЕСИ ПК*\n"
                . "───────────────────────────\n"
                . "⏳ *Закриваю процес (PID: {$pid})...*\n"
                . "Зачекайте, список оновлюється...";
            editOrSendMessage($chatId, $msgId, $loadingText, getMainKeyboard($chatId));
        } elseif ($data === 'menu_browser') {
            logAction($userId, $username, "Navigated Browser Menu");
            setSearchState($chatId, false);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
            editOrSendMessage($chatId, $msgId, "🌐 *КЕРУВАННЯ ВКЛАДКАМИ БРАУЗЕРА*\n\nКерує активним вікном Comet/Chrome (Ctrl+Tab / Ctrl+T / Ctrl+W).", getBrowserKeyboard());
        } elseif ($data === 'browser_prev_tab') {
            logAction($userId, $username, "Browser prev tab");
            setSearchState($chatId, false);
            addCommandToQueue('browser_tab', $chatId, ['action' => 'prev']);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '⬅️ Вкладка вліво (Ctrl+Shift+Tab)']);
        } elseif ($data === 'browser_next_tab') {
            logAction($userId, $username, "Browser next tab");
            setSearchState($chatId, false);
            addCommandToQueue('browser_tab', $chatId, ['action' => 'next']);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '➡️ Вкладка вправо (Ctrl+Tab)']);
        } elseif ($data === 'browser_new_tab') {
            logAction($userId, $username, "Browser new tab");
            setSearchState($chatId, false);
            addCommandToQueue('browser_tab', $chatId, ['action' => 'new']);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '➕ Нова вкладка (Ctrl+T)']);
        } elseif ($data === 'browser_close_tab') {
            logAction($userId, $username, "Browser close tab");
            setSearchState($chatId, false);
            addCommandToQueue('browser_tab', $chatId, ['action' => 'close']);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '❌ Закрити вкладку (Ctrl+W)']);
        } elseif ($data === 'browser_search_prompt') {
            logAction($userId, $username, "Activated Search Prompt");
            setSearchState($chatId, true);
            telegramApi('answerCallbackQuery', [
                'callback_query_id' => $cb['id'],
                'text' => '🔍 Надішліть ОДИН текстовий запит у чат'
            ]);
            editOrSendMessage(
                $chatId,
                $msgId,
                "🔍 *ПОШУК У БРАУЗЕРІ*\n\n"
                . "Напишіть *одним повідомленням* пошуковий запит.\n"
                . "Бот відкриє його в Comet і перейде на перший нерекламний результат.\n\n"
                . "⚠️ Наступні повідомлення *не* підуть у пошук — натисніть 🔍 ще раз.",
                getBrowserKeyboard()
            );
        } elseif ($data === 'menu_power') {
            setSearchState($chatId, false);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
            editOrSendMessage($chatId, $msgId, "⚡ *КЕРУВАННЯ ЖИВЛЕННЯМ ПК*", getPowerKeyboard());
        } elseif ($data === 'menu_audio') {
            logAction($userId, $username, "Opened Audio Devices Menu");
            setSearchState($chatId, false);
            $pcId = getSelectedPcId($chatId);
            $st = getSinglePcStatus($pcId);
            if ($st['online']) {
                addCommandToQueue('get_audio_devices', $chatId, ['msg_id' => $msgId]);
                telegramApi('answerCallbackQuery', [
                    'callback_query_id' => $cb['id'],
                    'text' => '⏳ Отримую пристрої звуку...'
                ]);
                $loadingText = "🔊 *ПРИСТРОЇ ВИВЕДЕННЯ ЗВУКУ*\n"
                    . "───────────────────────────\n"
                    . "⏳ *Завантаження списку пристроїв...*\n"
                    . "Зачекайте 1-2 секунди.";
                $loadingKb = [
                    'inline_keyboard' => [
                        [
                            ['text' => '🔄 Оновити', 'callback_data' => 'menu_audio'],
                            ['text' => '« Головне меню', 'callback_data' => 'menu_main']
                        ]
                    ]
                ];
                editOrSendMessage($chatId, $msgId, $loadingText, $loadingKb);
            } else {
                $statusText = "🔊 *ПРИСТРОЇ ВИВЕДЕННЯ ЗВУКУ*\n"
                    . "───────────────────────────\n"
                    . "🔴 *Статус:* ПК вимкнено або агент офлайн\n"
                    . "⏱️ *Востаннє у мережі:* `" . $st['last_seen_date'] . "`\n";
                telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
                editOrSendMessage($chatId, $msgId, $statusText, getMainKeyboard($chatId));
            }
        } elseif (strpos($data, 'select_audio_') === 0) {
            $deviceIndex = (int)str_replace('select_audio_', '', $data);
            logAction($userId, $username, "Switch audio device index: $deviceIndex");
            setSearchState($chatId, false);
            $pcId = getSelectedPcId($chatId);
            $st = getSinglePcStatus($pcId);
            if ($st['online']) {
                addCommandToQueue('set_audio_device', $chatId, [
                    'device_index' => $deviceIndex,
                    'msg_id' => $msgId
                ]);
                telegramApi('answerCallbackQuery', [
                    'callback_query_id' => $cb['id'],
                    'text' => "✅ Перемикаю пристрій #{$deviceIndex}..."
                ]);
            } else {
                telegramApi('answerCallbackQuery', [
                    'callback_query_id' => $cb['id'],
                    'text' => '🔴 ПК офлайн'
                ]);
            }
        } elseif ($data === 'power_wol' || $data === 'turn_on_pc') {
            logAction($userId, $username, "Sent Wake-On-LAN packet");
            $wol_url = "https://driver.lutsk.ua/img/bot/newfix/wol.php?mac=" . urlencode($PC_MAC) . "&ip=" . urlencode($PUBLIC_IP);
            @file_get_contents($wol_url);
            $targetIp = $PUBLIC_IP ?: '255.255.255.255';
            sendWakeOnLan($PC_MAC, $targetIp, $PC_PORT);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '⚡ Сигнал Wake-on-LAN надіслано на ваш ПК!']);
        } elseif ($data === 'power_shutdown') {
            logAction($userId, $username, "Shutdown command");
            addCommandToQueue('shutdown', $chatId);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '🔴 Команду вимкнення ПК надіслано.']);
        } elseif ($data === 'power_sleep') {
            logAction($userId, $username, "Sleep command");
            addCommandToQueue('sleep', $chatId);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '🌙 ПК переводиться у режим сну.']);
        } elseif ($data === 'power_hibernate') {
            logAction($userId, $username, "Hibernate command");
            addCommandToQueue('hibernate', $chatId);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '❄️ ПК переводиться у режим гібернації.']);
        } elseif ($data === 'power_reboot') {
            logAction($userId, $username, "Reboot command");
            addCommandToQueue('reboot', $chatId);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '🔄 ПК перезавантажується.']);
        } elseif ($data === 'power_lock') {
            logAction($userId, $username, "Lock screen");
            addCommandToQueue('lock', $chatId);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '🔒 Екран заблоковано.']);
        } elseif ($data === 'power_unlock') {
            logAction($userId, $username, "Unlock screen");
            addCommandToQueue('unlock', $chatId);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '🔑 Екран розблоковано!']);
        } elseif ($data === 'menu_status') {
            logAction($userId, $username, "Checked Status");
            $pcId = getSelectedPcId($chatId);
            $st = getSinglePcStatus($pcId);
            if ($st['online']) {
                addCommandToQueue('status', $chatId);
                telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '⏳ Оновлюю стан ПК...']);
            } else {
                $statusText = "📊 *СТАН ПК*\n"
                    . "───────────────────────────\n"
                    . "🔴 *Статус:* ПК вимкнено або агент офлайн\n"
                    . "⏱️ *Востаннє у мережі:* `" . $st['last_seen_date'] . "`\n"
                    . "💡 *Порада:* Натисніть *'⚡ Увімкнути ПК (Wake-on-LAN)'* у меню живлення.";
                telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
                editOrSendMessage($chatId, $msgId, $statusText, getMainKeyboard($chatId));
            }
        } elseif ($data === 'menu_apps') {
            setSearchState($chatId, false);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
            editOrSendMessage($chatId, $msgId, "🚀 *ЗАПУСК ПРОГРАМ НА ПК*\n\nЯкщо програма вже відкрита — лише фокус вікна (без нового екземпляра).", getAppsKeyboard());
        } elseif (strpos($data, 'app_') === 0) {
            setSearchState($chatId, false);
            $appName = str_replace('app_', '', $data);
            logAction($userId, $username, "Launched app: $appName");
            if ($appName === 'ytmusic') {
                // Simply open YouTube Music in a new tab (no search for existing tabs)
                addCommandToQueue('open_app', $chatId, [
                    'app' => $appName,
                    'yt_url' => $YT_MUSIC_URL
                ]);
                telegramApi('answerCallbackQuery', [
                    'callback_query_id' => $cb['id'],
                    'text' => '🎧 Відкриваю YouTube Music'
                ]);
            } else {
                addCommandToQueue('open_app', $chatId, [
                    'app' => $appName,
                    'yt_url' => $YT_MUSIC_URL,
                    'focus_only' => true
                ]);
                telegramApi('answerCallbackQuery', [
                    'callback_query_id' => $cb['id'],
                    'text' => "🚀 Фокус/запуск: $appName"
                ]);
            }
        } elseif ($data === 'menu_music') {
            setSearchState($chatId, false);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
            editOrSendMessage($chatId, $msgId, "🎵 *МЕНЮ МУЗИКИ*", getMusicKeyboard());
        } elseif ($data === 'menu_movies') {
            setSearchState($chatId, false);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id']]);
            editOrSendMessage($chatId, $msgId, "🎬 *МЕНЮ ФІЛЬМІВ ТА СЕРІАЛІВ*", getMoviesKeyboard());
        } elseif (strpos($data, 'media_') === 0) {
            $act = str_replace('media_', '', $data);
            logAction($userId, $username, "Media action: $act");
            addCommandToQueue('media', $chatId, ['action' => $act]);
            
            $toastText = "Натиснуто: $act";
            if ($act === 'rewind') $toastText = "⏪ Перемотка назад (5 сек)";
            elseif ($act === 'forward') $toastText = "⏩ Перемотка вперед (5 сек)";
            elseif ($act === 'play') $toastText = "⏯️ Пауза / Плей";
            elseif ($act === 'music_play') $toastText = "⏯️ Пауза / Плей (Музика)";
            elseif ($act === 'music_prev') $toastText = "⏮️ Попередній трек (Музика)";
            elseif ($act === 'music_next') $toastText = "⏭️ Наступний трек (Музика)";
            elseif ($act === 'vup') $toastText = "🔊 Гучність +10%";
            elseif ($act === 'vdown') $toastText = "🔉 Гучність -10%";
            elseif ($act === 'mute') $toastText = "🔇 Без звуку";
            elseif ($act === 'prev') $toastText = "⏮️ Попередній трек";
            elseif ($act === 'next') $toastText = "⏭️ Наступний трек";
            elseif ($act === 'fullscreen') $toastText = "🖥️ Повний екран (F)";
            elseif ($act === 'scroll_up') $toastText = "🔼 Скрол вгору";
            elseif ($act === 'scroll_down') $toastText = "🔽 Скрол вниз";

            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => $toastText]);
        } elseif ($data === 'menu_screenshot') {
            logAction($userId, $username, "Requested Screenshot");
            addCommandToQueue('screenshot', $chatId, ['msg_id' => $msgId]);
            telegramApi('answerCallbackQuery', ['callback_query_id' => $cb['id'], 'text' => '📸 Робиться скріншот екрана...']);
        } elseif ($data === 'menu_net') {
            logAction($userId, $username, "Checked Network Info");
            $pcId = getSelectedPcId($chatId);
            $st = getSinglePcStatus($pcId);
            $netInfo = "🌐 *МЕРЕЖЕВА ІНФОРМАЦІЯ*\n"
                . "───────────────────────────\n"
                . "🖥️ *ПК:* `{$st['name']}`\n"
                . "📡 *Агент ПК:* " . ($st['online'] ? '🟢 Активний' : '🔴 Офлайн') . "\n"
                .