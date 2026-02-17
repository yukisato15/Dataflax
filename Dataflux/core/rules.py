#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rule processing logic for advanced file operations
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import json
from datetime import datetime


@dataclass
class ProcessingRule:
    """処理ルール定義"""
    id: str
    name: str
    description: str
    condition: Dict[str, Any]
    action: Dict[str, Any]
    enabled: bool = True
    priority: int = 0


class RuleEngine:
    """ルールエンジン"""
    
    def __init__(self):
        self.rules: List[ProcessingRule] = []
        self.load_default_rules()
    
    def load_default_rules(self):
        """デフォルトルールを読み込み"""
        default_rules = [
            ProcessingRule(
                id="large_video_isolation",
                name="大容量動画ファイル分離",
                description="100MB以上の動画ファイルを専用フォルダに移動",
                condition={
                    "media_type": "video",
                    "min_size_mb": 100
                },
                action={
                    "operation": "move",
                    "target_dir": "large_videos"
                },
                priority=1
            ),
            ProcessingRule(
                id="raw_audio_separation",
                name="RAW音声ファイル分離",
                description="WAV/AIFF形式の音声ファイルを分離",
                condition={
                    "extensions": [".wav", ".aiff", ".aif"]
                },
                action={
                    "operation": "copy",
                    "target_dir": "raw_audio"
                },
                priority=2
            ),
            ProcessingRule(
                id="small_image_collection",
                name="小サイズ画像収集",
                description="5MB未満の画像ファイルを収集",
                condition={
                    "media_type": "image",
                    "max_size_mb": 5
                },
                action={
                    "operation": "copy",
                    "target_dir": "small_images"
                },
                priority=3
            ),
            ProcessingRule(
                id="document_organization",
                name="文書ファイル整理",
                description="文書ファイルを拡張子別に分類",
                condition={
                    "media_type": "document"
                },
                action={
                    "operation": "move",
                    "target_dir": "documents/{extension}"
                },
                priority=4
            ),
            ProcessingRule(
                id="old_file_archiving",
                name="古いファイルのアーカイブ",
                description="1年以上更新されていないファイルをアーカイブ",
                condition={
                    "older_than_days": 365
                },
                action={
                    "operation": "move",
                    "target_dir": "archive/{year}"
                },
                priority=5
            )
        ]
        
        self.rules.extend(default_rules)
    
    def add_rule(self, rule: ProcessingRule):
        """ルールを追加"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)
    
    def remove_rule(self, rule_id: str) -> bool:
        """ルールを削除"""
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                del self.rules[i]
                return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional[ProcessingRule]:
        """IDでルールを取得"""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None
    
    def get_enabled_rules(self) -> List[ProcessingRule]:
        """有効なルールを取得"""
        return [rule for rule in self.rules if rule.enabled]
    
    def evaluate_file(self, file_path: Path, file_info: Dict[str, Any]) -> List[ProcessingRule]:
        """ファイルに適用されるルールを評価"""
        matching_rules = []
        
        for rule in self.get_enabled_rules():
            if self._matches_condition(file_path, file_info, rule.condition):
                matching_rules.append(rule)
        
        return matching_rules
    
    def _matches_condition(self, file_path: Path, file_info: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        """条件にマッチするかチェック"""
        # 媒体タイプチェック
        if "media_type" in condition:
            if file_info.get("media_type") != condition["media_type"]:
                return False
        
        # 拡張子チェック
        if "extensions" in condition:
            if file_path.suffix.lower() not in condition["extensions"]:
                return False
        
        # サイズチェック
        file_size_mb = file_info.get("size", 0) / (1024 * 1024)
        if "min_size_mb" in condition:
            if file_size_mb < condition["min_size_mb"]:
                return False
        
        if "max_size_mb" in condition:
            if file_size_mb > condition["max_size_mb"]:
                return False
        
        # 日付チェック
        if "older_than_days" in condition:
            try:
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                days_old = (datetime.now() - file_mtime).days
                if days_old < condition["older_than_days"]:
                    return False
            except:
                return False
        
        if "newer_than_days" in condition:
            try:
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                days_old = (datetime.now() - file_mtime).days
                if days_old > condition["newer_than_days"]:
                    return False
            except:
                return False
        
        return True
    
    def apply_rules(
        self, 
        files_info: List[Dict[str, Any]], 
        base_target_dir: Path,
        dry_run: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """ルールを適用してファイル処理を実行"""
        results = {
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "operations": [],
            "by_rule": {}
        }
        
        total_files = len(files_info)
        
        for i, file_info in enumerate(files_info):
            try:
                file_path = Path(file_info["path"])
                matching_rules = self.evaluate_file(file_path, file_info)
                
                if not matching_rules:
                    results["skipped"] += 1
                    continue
                
                # 最初にマッチしたルールを適用（優先度順）
                rule = matching_rules[0]
                target_path = self._generate_target_path(file_path, rule.action, base_target_dir, file_info)
                
                operation = {
                    "source": str(file_path),
                    "target": str(target_path),
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "operation": rule.action["operation"],
                    "timestamp": datetime.now().isoformat()
                }
                
                if not dry_run:
                    self._execute_operation(file_path, target_path, rule.action["operation"])
                
                results["processed"] += 1
                results["operations"].append(operation)
                results["by_rule"].setdefault(rule.id, 0)
                results["by_rule"][rule.id] += 1
                
                if progress_callback:
                    progress = int((i + 1) / total_files * 100)
                    progress_callback(progress, f"ルール適用中: {rule.name}")
                    
            except Exception as e:
                results["errors"] += 1
                error_op = {
                    "source": file_info.get("path", "unknown"),
                    "error": str(e),
                    "operation": "rule_error"
                }
                results["operations"].append(error_op)
        
        return results
    
    def _generate_target_path(self, file_path: Path, action: Dict[str, Any], base_dir: Path, file_info: Dict[str, Any]) -> Path:
        """ターゲットパスを生成"""
        target_template = action["target_dir"]
        
        # プレースホルダーの置換
        replacements = {
            "{extension}": file_path.suffix.lower().lstrip('.'),
            "{media_type}": file_info.get("media_type", "other"),
            "{year}": str(datetime.fromtimestamp(file_path.stat().st_mtime).year),
            "{month}": f"{datetime.fromtimestamp(file_path.stat().st_mtime).month:02d}",
        }
        
        for placeholder, value in replacements.items():
            target_template = target_template.replace(placeholder, value)
        
        target_dir = base_dir / target_template
        return self._get_unique_path(target_dir, file_path.name)
    
    def _get_unique_path(self, target_dir: Path, filename: str) -> Path:
        """重複しないパスを生成"""
        target_dir.mkdir(parents=True, exist_ok=True)
        
        base_path = target_dir / filename
        if not base_path.exists():
            return base_path
        
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1
        
        while True:
            new_filename = f"{stem}_{counter:02d}{suffix}"
            new_path = target_dir / new_filename
            if not new_path.exists():
                return new_path
            counter += 1
    
    def _execute_operation(self, source: Path, target: Path, operation: str):
        """実際のファイル操作を実行"""
        target.parent.mkdir(parents=True, exist_ok=True)
        
        if operation == "move":
            import shutil
            shutil.move(str(source), str(target))
        elif operation == "copy":
            import shutil
            shutil.copy2(str(source), str(target))
        elif operation == "link":
            if hasattr(source, "link_to"):  # Python 3.10+
                target.hardlink_to(source)
            else:
                source.link_to(target)
    
    def save_rules(self, file_path: Path):
        """ルールをJSONファイルに保存"""
        rules_data = []
        for rule in self.rules:
            rule_dict = {
                "id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "condition": rule.condition,
                "action": rule.action,
                "enabled": rule.enabled,
                "priority": rule.priority
            }
            rules_data.append(rule_dict)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, indent=2, ensure_ascii=False)
    
    def load_rules(self, file_path: Path):
        """JSONファイルからルールを読み込み"""
        if not file_path.exists():
            return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            rules_data = json.load(f)
        
        self.rules.clear()
        for rule_dict in rules_data:
            rule = ProcessingRule(**rule_dict)
            self.rules.append(rule)
        
        self.rules.sort(key=lambda r: r.priority)