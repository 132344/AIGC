import yaml
import os
import requests
import uuid
from typing import Union
from qdrant_client import QdrantClient, models
from qdrant_client.models import VectorParams, Distance, PointStruct

class QdrantManager:
    def __init__(self, config_path="config.yaml", reload_books=True):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.api_key = self.config["api"]["siliconflow"]["api_key"]
        self.base_url = self.config["api"]["siliconflow"]["base_url"]
        self.embedding_model = self.config["model"]["embedding"]["model_name"]
        self.vector_size = self.config["qdrant"]["vector_params"]["size"]

        self.clients = {}
        self.role_dirs = {}
        self.role_names = {}
        self.reload_books_on_init = reload_books # 保存开关状态

        self._init_structure()

    def _init_structure(self):
        """
        核心修改：统一初始化所有角色的文件和数据库结构。
        - 文件夹名使用别名。
        - 自动创建缺失的提示词和知识库文件。
        - 自动填充默认提示词。
        """
        current_dir = os.getcwd()
        list_dir = os.path.join(current_dir, "list")
        os.makedirs(list_dir, exist_ok=True)

        db_roles = self.config.get("qdrant", {}).get("db", {})
        for role_alias, role_name in db_roles.items():
            self.role_names[role_alias] = role_name

            # 1. 角色文件夹的名字使用别名 (e.g., list/fy)
            role_dir = os.path.join(list_dir, role_alias)
            os.makedirs(role_dir, exist_ok=True)
            self.role_dirs[role_alias] = role_dir

            # 2. 检查并创建提示词文件，如果不存在则填入默认内容
            prompt_file_path = os.path.join(role_dir, f"{role_name}.txt")
            if not os.path.exists(prompt_file_path):
                with open(prompt_file_path, 'w', encoding='utf-8') as f:
                    f.write(f"你是{role_name}")
                print(f"已创建并填充默认提示词: {prompt_file_path}")

            # 3. 检查并创建知识库文件（如果不存在）
            book_file_path = os.path.join(role_dir, f"{role_name}_db_book.txt")
            if not os.path.exists(book_file_path):
                open(book_file_path, 'w').close()
                print(f"已创建空的知识库文件: {book_file_path}")

            # 初始化Qdrant客户端和集合
            qdrant_storage_path = os.path.join(role_dir, "qdrant_storage")
            os.makedirs(qdrant_storage_path, exist_ok=True)
            client = QdrantClient(path=qdrant_storage_path)
            self.clients[role_alias] = client
            self._create_collections_for_role(role_alias)

    def _create_collections_for_role(self, role_alias: str):
        """为一个角色创建或确认两个核心集合的存在，使用别名命名"""
        client = self.clients[role_alias]
        db_collection = f"{role_alias}_db"
        
        if not self._is_collection_exist(client, db_collection):
            client.create_collection(
                collection_name=db_collection,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )
            print(f"成功创建动态数据库集合: {db_collection}")

        if self.reload_books_on_init:
            self.reload_knowledge_base(role_alias)

    def _is_collection_exist(self, client: QdrantClient, collection_name: str) -> bool:
        try:
            client.get_collection(collection_name=collection_name)
            return True
        except Exception:
            return False

    def embed_text(self, text: str):
        url = f"{self.base_url}/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {"model": self.embedding_model, "input": text}
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
        except Exception as e:
            print(f"向量生成失败：{str(e)}")
            return None

    def add_point_to_db(self, role_alias: str, text: str, metadata: dict = None) -> Union[str, None]:
        client = self.clients.get(role_alias)
        if not client:
            print(f"警告：角色别名 {role_alias} 对应的客户端不存在")
            return None
        embedding = self.embed_text(text)
        if not embedding:
            print(f"警告：文本「{text}」向量生成失败，跳过")
            return None
        point_id = str(uuid.uuid4())
        collection_name = f"{role_alias}_db"
        payload = {"text": text, "source_collection": collection_name} # 优化：添加来源集合
        if metadata:
            payload.update(metadata)
        client.upsert(
            collection_name=collection_name,
            points=[PointStruct(id=point_id, vector=embedding, payload=payload)]
        )
        print(f"成功向 {collection_name} 添加数据点: {point_id}")
        return point_id

    def update_point_in_db(self, role_alias: str, point_id: str, new_text: str, new_metadata: dict = None) -> str:
        client = self.clients.get(role_alias)
        if not client:
            return "更新失败：客户端不存在"
        new_embedding = self.embed_text(new_text)
        if not new_embedding:
            return "更新失败：文本向量生成失败"
        collection_name = f"{role_alias}_db"
        payload = {"text": new_text, "source_collection": collection_name}
        if new_metadata:
            payload.update(new_metadata)
        try:
            client.upsert(
                collection_name=collection_name,
                points=[PointStruct(id=point_id, vector=new_embedding, payload=payload)]
            )
            print(f"成功更新 {collection_name} 中ID为 {point_id} 的数据")
            return f"更新成功"
        except Exception as e:
            return f"更新失败：写入数据库时发生错误: {e}"

    def update_point_by_text(self, role_alias: str, old_text: str, new_text: str, new_metadata: dict = None) -> str:
        """
        通过文本内容查找并更新一个数据点。
        此方法只能更新角色记忆数据库({role_alias}_db)。
        如果找到多个匹配项，为了安全，只更新第一个。
        返回一个表示操作结果的字符串。
        """
        client = self.clients.get(role_alias)
        if not client:
            return f"更新失败：角色别名 {role_alias} 对应的客户端不存在"

        collection_name = f"{role_alias}_db"
        
        # 1. 通过 scroll API 和 filter 查找匹配的点的ID
        try:
            found_points, _ = client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(key="text", match=models.MatchValue(value=old_text))
                    ]
                ),
                limit=1,
                with_payload=False,
                with_vectors=False
            )
        except Exception as e:
            return f"更新失败：通过文本查找数据点时出错: {e}"

        # 2. 检查查找结果
        if not found_points:
            return f"更新失败：在 {collection_name} 中未找到内容为“{old_text}”的数据点。"
        
        point_to_update = found_points[0]
        point_id = point_to_update.id
        
        # 3. 调用现有的按ID更新的方法
        print(f"已找到匹配内容的数据点 (ID: {point_id})，现在进行更新...")
        return self.update_point_in_db(role_alias, point_id, new_text, new_metadata)

    def delete_point_from_db(self, role_alias: str, point_id: str):
        client = self.clients.get(role_alias)
        if not client: return
        collection_name = f"{role_alias}_db"
        client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=[point_id]),
        )
        print(f"已尝试从 {collection_name} 删除数据点: {point_id}")

    def search(self, role_alias: str, query: str, top_k=3):
        client = self.clients.get(role_alias)
        if not client: return {"error": f"角色别名 {role_alias} 对应的向量数据库不存在"}
        query_vector = self.embed_text(query)
        if not query_vector: return {"error": "查询文本向量生成失败"}
        all_results = []
        db_collection = f"{role_alias}_db"
        book_collection = f"{role_alias}_db_book"
        for collection_name in [db_collection, book_collection]:
            if self._is_collection_exist(client, collection_name):
                try:
                    results = client.search(collection_name=collection_name, query_vector=query_vector, limit=top_k)
                    all_results.extend(results)
                except Exception as e:
                    print(f"搜索集合 {collection_name} 出错: {e}")
        all_results.sort(key=lambda r: r.score, reverse=True)
        return [{"id": str(r.id), "text": (r.payload or {}).get("text", ""), "score": float(r.score or 0.0), "source_collection": r.payload.get("source_collection")} for r in all_results[:top_k]]

    def reload_knowledge_base(self, role_alias: str):
        client = self.clients.get(role_alias)
        if not client: return
        book_collection = f"{role_alias}_db_book"
        if self._is_collection_exist(client, book_collection):
            client.delete_collection(collection_name=book_collection)
        client.create_collection(
            collection_name=book_collection,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
        )
        print(f"已重载知识库集合: {book_collection}")
        role_name = self.role_names.get(role_alias)
        role_dir = self.role_dirs.get(role_alias)
        book_file_path = os.path.join(role_dir, f"{role_name}_db_book.txt")
        try:
            points_to_add = []
            with open(book_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    embedding = self.embed_text(line)
                    if embedding:
                        points_to_add.append(PointStruct(id=str(uuid.uuid4()), vector=embedding, payload={"text": line, "source_collection": book_collection}))
            if points_to_add:
                client.upsert(collection_name=book_collection, points=points_to_add)
                print(f"成功向 {book_collection} 加载 {len(points_to_add)} 条知识库数据")
        except Exception as e:
            print(f"加载 {role_alias} 知识库失败：{str(e)}")

    def close(self):
        for client in self.clients.values():
            if client: client.close()
        print("所有Qdrant客户端已关闭")

if __name__ == '__main__':
    print("--- 初始化 QdrantManager ---")
    manager = QdrantManager()
# ---------------------------
    test_alias = 'ynf'
    if test_alias not in manager.clients:
        print(f"错误：测试别名 '{test_alias}' 未在 config.yaml 中配置或初始化失败。")
    else:
        print(f"\n--- 测试 '{test_alias}' 知识库覆盖加载 ---")
    print(f"\n--- 查看最终数据量 ---")
    client = manager.clients[test_alias]
    db_count = client.count(collection_name=f"{test_alias}_db", exact=True).count
    print(f"集合 '{test_alias}_db' 总条数: {db_count}")
    book_count = client.count(collection_name=f"{test_alias}_db_book", exact=True).count
    print(f"集合 '{test_alias}_db_book' 总条数: {book_count}")
# ---------------------------
    test_alias = 'ss'
    if test_alias not in manager.clients:
        print(f"错误：测试别名 '{test_alias}' 未在 config.yaml 中配置或初始化失败。")
    else:
        print(f"\n--- 测试 '{test_alias}' 知识库覆盖加载 ---")
    print(f"\n--- 查看最终数据量 ---")
    client = manager.clients[test_alias]
    db_count = client.count(collection_name=f"{test_alias}_db", exact=True).count
    print(f"集合 '{test_alias}_db' 总条数: {db_count}")
    book_count = client.count(collection_name=f"{test_alias}_db_book", exact=True).count
    print(f"集合 '{test_alias}_db_book' 总条数: {book_count}")
# ---------------------------
    test_alias = 'zgl'
    if test_alias not in manager.clients:
        print(f"错误：测试别名 '{test_alias}' 未在 config.yaml 中配置或初始化失败。")
    else:
        print(f"\n--- 测试 '{test_alias}' 知识库覆盖加载 ---")
    print(f"\n--- 查看最终数据量 ---")
    client = manager.clients[test_alias]
    db_count = client.count(collection_name=f"{test_alias}_db", exact=True).count
    print(f"集合 '{test_alias}_db' 总条数: {db_count}")
    book_count = client.count(collection_name=f"{test_alias}_db_book", exact=True).count
    print(f"集合 '{test_alias}_db_book' 总条数: {book_count}")
    manager.close()
