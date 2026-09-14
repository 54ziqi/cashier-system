// Prevents additional console window in Windows release mode
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    qihhao_cashier_lib::run()
}
