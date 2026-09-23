#!/usr/bin/env python3
"""单元测试：验证连接复用池、自动重试与多图并发批量执行机制。"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import generate_image


class TestConnectionPoolAndHttpClient(unittest.TestCase):
    """测试网络层长连接复用与指数退避重试。"""

    def test_connection_pool_lifecycle(self):
        pool = generate_image.ConnectionPool(maxsize=4, timeout=10.0)
        conn1 = pool.acquire("http", "example.com", 80)
        self.assertIsNotNone(conn1)
        # Release back to pool
        pool.release("http", "example.com", 80, conn1, close=False)
        # Re-acquire should get the same or reusable connection
        conn2 = pool.acquire("http", "example.com", 80)
        self.assertEqual(conn1, conn2)
        pool.release("http", "example.com", 80, conn2, close=False)
        pool.close_all()

    @patch.object(generate_image.HttpClient, "_execute_http")
    def test_http_client_retry_on_transient_502(self, mock_exec):
        # 模拟前两次返回 502，第三次返回 200
        mock_exec.side_effect = [
            (502, {}, b"Bad Gateway", False),
            (502, {}, b"Bad Gateway", False),
            (200, {}, b'{"data": [{"b64_json": "AAAA"}]}', False),
        ]

        client = generate_image.HttpClient(max_retries=3, retry_delay=0.01)
        result, retries = client.post_json(
            "https://api.example.com/v1/images/generations",
            api_key="sk-test",
            payload={"prompt": "test"},
        )
        self.assertEqual(retries, 2)
        self.assertIn("data", result)
        self.assertEqual(mock_exec.call_count, 3)
        client.close()

    @patch.object(generate_image.HttpClient, "_execute_http")
    def test_http_client_fail_immediately_on_400(self, mock_exec):
        # 400 Bad Request 不属于可重试错误，必须立即大声报错
        mock_exec.return_value = (400, {}, b'{"error": "Invalid prompt"}', False)

        client = generate_image.HttpClient(max_retries=3, retry_delay=0.01)
        with self.assertRaises(generate_image.ImageApiError) as ctx:
            client.post_json(
                "https://api.example.com/v1/images/generations",
                api_key="sk-test",
                payload={"prompt": "bad prompt"},
            )
        self.assertIn("400", str(ctx.exception))
        self.assertEqual(mock_exec.call_count, 1)
        client.close()


class TestBatchTaskCollection(unittest.TestCase):
    """测试从目录和清单文件提取批量任务。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.base_path = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_collect_batch_tasks_from_dir(self):
        prompts_dir = self.base_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "01-hero-main.txt").write_text("main prompt 1", encoding="utf-8")
        (prompts_dir / "02-feature-main.txt").write_text("main prompt 2", encoding="utf-8")
        (prompts_dir / "10-detail-above-fold.txt").write_text("detail prompt 10", encoding="utf-8")
        (prompts_dir / "03-angle-sheet.txt").write_text("angle sheet prompt", encoding="utf-8")

        mock_args = MagicMock()
        mock_args.asset_type = "custom"
        mock_args.quality = None
        mock_args.format = "png"
        mock_args.n = 1
        mock_args.image = None
        mock_args._size_explicit = False

        tasks = generate_image.collect_batch_tasks_from_dir(prompts_dir, mock_args)
        self.assertEqual(len(tasks), 4)

        # 检查自然排序
        task_names = [t.source_name for t in tasks]
        self.assertEqual(
            task_names,
            ["01-hero-main", "02-feature-main", "03-angle-sheet", "10-detail-above-fold"],
        )

        # 检查资产类型与尺寸自动推导
        self.assertEqual(tasks[0].asset_type, "main")
        self.assertEqual(tasks[0].size, "1024x1024")

        self.assertEqual(tasks[2].asset_type, "angle-sheet")

        self.assertEqual(tasks[3].asset_type, "detail")
        self.assertEqual(tasks[3].size, "1024x1536")

    def test_collect_batch_tasks_from_manifest_json(self):
        manifest_file = self.base_path / "manifest.json"
        manifest_data = [
            {"name": "m1", "prompt": "main image", "asset_type": "main", "size": "1024x1024"},
            {"name": "d1", "prompt": "detail image", "asset_type": "detail", "size": "1024x1536"},
        ]
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        mock_args = MagicMock()
        mock_args.asset_type = "custom"
        mock_args.quality = None
        mock_args.format = "png"
        mock_args.n = 1
        mock_args.image = None
        mock_args._size_explicit = False

        tasks = generate_image.collect_batch_tasks_from_file(manifest_file, mock_args)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].source_name, "m1")
        self.assertEqual(tasks[0].asset_type, "main")
        self.assertEqual(tasks[1].source_name, "d1")
        self.assertEqual(tasks[1].asset_type, "detail")
        self.assertEqual(tasks[1].size, "1024x1536")


class TestBatchExecutionPipeline(unittest.TestCase):
    """测试多线程并发执行与故障隔离机制。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.job_dir = Path(self.test_dir) / "job-output"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_execute_batch_prompt_only(self):
        tasks = [
            generate_image.BatchTask(
                task_id="01-task",
                prompt="prompt text 1",
                asset_type="main",
                source_name="task-1",
                size="1024x1024",
            )
        ]
        mock_args = MagicMock()
        mock_args.mode = "prompt"
        mock_args.job_dir = str(self.job_dir)
        mock_args.concurrency = 2
        mock_args.max_retries = 3
        mock_args.retry_delay = 0.1
        mock_args.timeout = 10.0

        exit_code = generate_image.execute_batch(tasks, mock_args, {}, [])
        self.assertEqual(exit_code, 0)
        self.assertTrue((self.job_dir / "prompts").is_dir())
        saved_files = list((self.job_dir / "prompts").glob("*.txt"))
        self.assertEqual(len(saved_files), 1)

    @patch.object(generate_image.HttpClient, "_execute_http")
    def test_execute_batch_with_fault_isolation(self, mock_exec):
        # 任务 1 成功，任务 2 失败（400），任务 3 成功
        def side_effect(url, method, headers, body):
            payload = json.loads(body.decode("utf-8")) if body else {}
            prompt = payload.get("prompt", "")
            if "fail" in prompt:
                return (400, {}, b'{"error": "Simulated error"}', False)
            import base64
            # 模拟 1x1 png base64
            dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            return (200, {}, json.dumps({"data": [{"b64_json": dummy_b64}]}).encode("utf-8"), False)

        mock_exec.side_effect = side_effect

        tasks = [
            generate_image.BatchTask("01-ok", "ok prompt 1", "main", "ok-1", "1024x1024"),
            generate_image.BatchTask("02-bad", "fail prompt 2", "detail", "bad-2", "1024x1536"),
            generate_image.BatchTask("03-ok", "ok prompt 3", "detail", "ok-3", "1024x1536"),
        ]

        mock_args = MagicMock()
        mock_args.mode = "image"
        mock_args.job_dir = str(self.job_dir)
        mock_args.concurrency = 3
        mock_args.max_retries = 1
        mock_args.retry_delay = 0.01
        mock_args.timeout = 10.0

        config = {
            generate_image.ENV_BASE_URL: "https://api.example.com/v1",
            generate_image.ENV_MODEL: "gpt-image-1.5",
            generate_image.ENV_API_KEY: "sk-test",
        }

        exit_code = generate_image.execute_batch(tasks, mock_args, config, [])
        # 存在失败任务时，退出码为 2
        self.assertEqual(exit_code, 2)

        # 检查 batch-summary.json
        summary_file = self.job_dir / "batch-summary.json"
        self.assertTrue(summary_file.is_file())
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["succeeded"], 2)
        self.assertEqual(summary["failed"], 1)

        # 检查成功生成的文件
        main_images = list((self.job_dir / "main").glob("*.png"))
        self.assertEqual(len(main_images), 1)

        detail_images = list((self.job_dir / "detail").glob("*.png"))
        self.assertEqual(len(detail_images), 1)




class TestEdgeCasesAndCli(unittest.TestCase):
    """边缘场景与 CLI 解析测试。"""

    def test_cli_parsing_batch_options(self):
        with patch.object(sys, "argv", [
            "generate_image.py",
            "--batch-dir", "dummy_prompts",
            "--concurrency", "4",
            "--max-retries", "5",
            "--retry-delay", "1.5",
            "--timeout", "60",
        ]):
            args = generate_image.parse_args()
            self.assertEqual(args.batch_dir, "dummy_prompts")
            self.assertEqual(args.concurrency, 4)
            self.assertEqual(args.max_retries, 5)
            self.assertEqual(args.retry_delay, 1.5)
            self.assertEqual(args.timeout, 60.0)

    @patch.object(generate_image.HttpClient, "_execute_http")
    def test_http_client_429_retry_after(self, mock_exec):
        # 模拟 429 带有 Retry-After: 0.1
        mock_exec.side_effect = [
            (429, {"retry-after": "0.1"}, b"Rate limit exceeded", False),
            (200, {}, b'{"data": [{"b64_json": "AAAA"}]}', False),
        ]

        client = generate_image.HttpClient(max_retries=2, retry_delay=0.5)
        result, retries = client.post_json(
            "https://api.example.com/v1/images/generations",
            api_key="sk-test",
            payload={"prompt": "test"},
        )
        self.assertEqual(retries, 1)
        self.assertIn("data", result)
        self.assertEqual(mock_exec.call_count, 2)
        client.close()

    def test_download_bytes_with_redirect(self):
        client = generate_image.HttpClient(max_retries=1)
        with patch.object(client, "_execute_http") as mock_exec:
            mock_exec.side_effect = [
                (302, {"location": "https://cdn.example.com/actual.png"}, b"", False),
                (200, {}, b"IMAGE_DATA_BYTES", False),
            ]
            data = client.download_bytes("https://api.example.com/redirect-to-cdn")
            self.assertEqual(data, b"IMAGE_DATA_BYTES")
            self.assertEqual(mock_exec.call_count, 2)
        client.close()


if __name__ == "__main__":
    unittest.main()
